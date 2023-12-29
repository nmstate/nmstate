// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use super::super::{
    device::create_index_for_nm_devs,
    dns::{
        cur_dns_ifaces_still_valid_for_dns, store_dns_config_to_iface,
        store_dns_search_or_option_to_iface,
    },
    error::nm_error_to_nmstate,
    nm_dbus::{NmApi, NmConnection},
    profile::{perpare_nm_conns, PerparedNmConnections},
    query_apply::{
        activate_nm_profiles, create_index_for_nm_conns_by_name_type,
        deactivate_nm_profiles, delete_exist_profiles, delete_orphan_ovs_ports,
        dispatch::apply_dispatch_script,
        dns::{
            is_iface_dns_desired, purge_global_dns_config,
            store_dns_config_via_global_api,
        },
        is_mptcp_flags_changed, is_mptcp_supported, is_route_removed,
        is_veth_peer_changed, is_vlan_changed, is_vrf_table_id_changed,
        is_vxlan_changed, save_nm_profiles,
        vpn::get_match_ipsec_nm_conn,
    },
    route::store_route_config,
    route_rule::store_route_rule_config,
    settings::{iface_type_to_nm, NM_SETTING_OVS_PORT_SETTING_NAME},
};

use crate::{
    InterfaceIdentifier, InterfaceType, MergedNetworkState, NmstateError,
};

// There is plan to simply the `add_net_state`, `chg_net_state`, `del_net_state`
// `cur_net_state`, `des_net_state` into single struct. Suppress the clippy
// warning for now
pub(crate) fn nm_apply(
    merged_state: &MergedNetworkState,
    checkpoint: &str,
    timeout: u32,
) -> Result<(), NmstateError> {
    let mut nm_api = NmApi::new().map_err(nm_error_to_nmstate)?;
    nm_api.set_checkpoint(checkpoint, timeout);
    nm_api.set_checkpoint_auto_refresh(true);

    if !merged_state.memory_only {
        delete_ifaces(&mut nm_api, merged_state)?;
    }

    if let Some(hostname) = merged_state
        .hostname
        .desired
        .as_ref()
        .and_then(|c| c.config.as_ref())
    {
        if merged_state.memory_only {
            log::debug!(
                "NM: Cannot change configure hostname in memory only mode, \
                ignoring"
            );
        } else {
            nm_api.hostname_set(hostname).map_err(nm_error_to_nmstate)?;
        }
    }

    let mptcp_supported = is_mptcp_supported(&nm_api);

    let exist_nm_conns =
        nm_api.connections_get().map_err(nm_error_to_nmstate)?;
    let nm_acs = nm_api
        .active_connections_get()
        .map_err(nm_error_to_nmstate)?;
    let nm_devs = nm_api.devices_get().map_err(nm_error_to_nmstate)?;

    let mut merged_state = merged_state.clone();

    store_route_config(&mut merged_state)?;

    store_route_rule_config(&mut merged_state)?;

    if merged_state.dns.is_changed()
        || !cur_dns_ifaces_still_valid_for_dns(&merged_state.interfaces)
    {
        purge_global_dns_config(&mut nm_api)?;

        if merged_state.dns.is_search_or_option_only() {
            // When user desire static DNS search and dynamic DNS nameserver,
            // we cannot use global DNS in this case because global DNS suppress
            // DNS nameserver learn from DHCP/autoconf.
            store_dns_search_or_option_to_iface(
                &mut merged_state,
                &nm_acs,
                &nm_devs,
            )?;
        } else if is_iface_dns_desired(&merged_state) {
            if let Err(e) =
                store_dns_config_to_iface(&mut merged_state, &nm_acs, &nm_devs)
            {
                log::info!(
                    "Cannot store DNS to interface profile: {e}, \
                    will try to set via global DNS"
                );
                store_dns_config_via_global_api(
                    &mut nm_api,
                    merged_state.dns.servers.as_slice(),
                    merged_state.dns.searches.as_slice(),
                    merged_state.dns.options.as_slice(),
                )?;
            }
        } else if merged_state
            .dns
            .desired
            .as_ref()
            .and_then(|d| d.config.as_ref())
            .map(|c| c.is_purge())
            == Some(true)
        {
            // Also need to purge interface level DNS
            store_dns_config_to_iface(&mut merged_state, &nm_acs, &nm_devs)
                .ok();
        } else {
            store_dns_config_via_global_api(
                &mut nm_api,
                merged_state.dns.servers.as_slice(),
                merged_state.dns.searches.as_slice(),
                merged_state.dns.options.as_slice(),
            )?;
        }
    }

    let PerparedNmConnections {
        to_store: nm_conns_to_store,
        to_activate: nm_conns_to_activate,
        to_deactivate: nm_conns_to_deactivate,
    } = perpare_nm_conns(
        &merged_state,
        exist_nm_conns.as_slice(),
        nm_acs.as_slice(),
        mptcp_supported,
        false,
    )?;

    let nm_ac_uuids: Vec<&str> =
        nm_acs.iter().map(|nm_ac| &nm_ac.uuid as &str).collect();
    let activated_nm_conns: Vec<&NmConnection> = exist_nm_conns
        .iter()
        .filter(|c| {
            if let Some(uuid) = c.uuid() {
                nm_ac_uuids.contains(&uuid)
            } else {
                false
            }
        })
        .collect();
    let nm_conns_to_deactivate_first = gen_nm_conn_need_to_deactivate_first(
        nm_conns_to_activate.as_slice(),
        activated_nm_conns.as_slice(),
    );
    deactivate_nm_profiles(
        &mut nm_api,
        nm_conns_to_deactivate_first.as_slice(),
    )?;

    save_nm_profiles(
        &mut nm_api,
        nm_conns_to_store.as_slice(),
        merged_state.memory_only,
    )?;
    if !merged_state.memory_only {
        delete_exist_profiles(
            &mut nm_api,
            &exist_nm_conns,
            &nm_conns_to_store,
        )?;
        delete_orphan_ovs_ports(
            &mut nm_api,
            &merged_state.interfaces,
            &exist_nm_conns,
            &nm_conns_to_activate,
        )?;
    }

    activate_nm_profiles(&mut nm_api, nm_conns_to_activate.as_slice())?;

    deactivate_nm_profiles(&mut nm_api, nm_conns_to_deactivate.as_slice())?;

    apply_dispatch_script(&merged_state.interfaces)?;

    Ok(())
}

fn delete_ifaces(
    nm_api: &mut NmApi,
    merged_state: &MergedNetworkState,
) -> Result<(), NmstateError> {
    let all_nm_conns = nm_api.connections_get().map_err(nm_error_to_nmstate)?;

    let nm_conns_name_type_index =
        create_index_for_nm_conns_by_name_type(&all_nm_conns);
    let mut uuids_to_delete: HashSet<&str> = HashSet::new();

    for merged_iface in merged_state
        .interfaces
        .iter()
        .filter(|i| i.is_changed() && i.merged.is_absent())
    {
        let iface = &merged_iface.merged;

        if iface.iface_type() == InterfaceType::Ipsec {
            for nm_conn in get_match_ipsec_nm_conn(iface.name(), &all_nm_conns)
            {
                if let Some(uuid) = nm_conn.uuid() {
                    uuids_to_delete.insert(uuid);
                }
            }
            continue;
        }

        // If interface type not mentioned, we delete all profile with interface
        // name
        let mut nm_conns_to_delete: Vec<&NmConnection> =
            if iface.iface_type() == InterfaceType::Unknown {
                all_nm_conns
                    .as_slice()
                    .iter()
                    .filter(|c| c.iface_name() == Some(iface.name()))
                    .collect()
            } else {
                let nm_iface_type = iface_type_to_nm(&iface.iface_type())?;
                nm_conns_name_type_index
                    .get(&(iface.name(), &nm_iface_type))
                    .cloned()
                    .unwrap_or_default()
            };
        // User might want to delete mac based interface using profile name
        if let Some(cur_iface) = &merged_iface.current {
            if cur_iface.base_iface().identifier
                == InterfaceIdentifier::MacAddress
                && cur_iface.base_iface().profile_name.as_deref()
                    == Some(iface.name())
            {
                for nm_conn in &all_nm_conns {
                    if nm_conn.id() == Some(iface.name()) {
                        nm_conns_to_delete.push(nm_conn);
                    }
                }
            }
        }
        // User might want to delete mac based interface using interface name
        if let Some(cur_iface) = &merged_iface.current {
            if cur_iface.base_iface().identifier
                == InterfaceIdentifier::MacAddress
                && cur_iface.base_iface().name.as_str() == iface.name()
            {
                if let Some(mac) = cur_iface.base_iface().mac_address.as_ref() {
                    for nm_conn in &all_nm_conns {
                        if nm_conn
                            .wired
                            .as_ref()
                            .and_then(|w| w.mac_address.as_ref())
                            .map(|s| s.to_uppercase())
                            == Some(mac.to_uppercase())
                        {
                            nm_conns_to_delete.push(nm_conn);
                        }
                    }
                }
            }
        }
        // Delete all existing connections for this interface
        for nm_conn in nm_conns_to_delete {
            if let Some(uuid) = nm_conn.uuid() {
                if !uuids_to_delete.contains(uuid) {
                    log::info!(
                        "Deleting NM connection for absent interface \
                        {}/{}: {}",
                        &iface.name(),
                        &iface.iface_type(),
                        uuid
                    );
                    uuids_to_delete.insert(uuid);
                }
            }
            // Delete OVS port profile along with OVS system and internal
            // Interface
            if nm_conn.controller_type() == Some("ovs-port") {
                // TODO: handle pre-exist OVS config using name instead of
                // UUID for controller
                if let Some(uuid) = nm_conn.controller() {
                    if !uuids_to_delete.contains(uuid) {
                        log::info!(
                            "Deleting NM OVS port connection {} \
                             for absent OVS interface {}",
                            uuid,
                            &iface.name(),
                        );
                        uuids_to_delete.insert(uuid);
                    }
                }
            }
        }
    }

    for uuid in &uuids_to_delete {
        nm_api
            .connection_delete(uuid)
            .map_err(nm_error_to_nmstate)?;
    }

    delete_orphan_ports(nm_api, &uuids_to_delete)?;
    delete_remain_virtual_interface_as_desired(nm_api, merged_state)?;
    Ok(())
}

fn delete_remain_virtual_interface_as_desired(
    nm_api: &mut NmApi,
    merged_state: &MergedNetworkState,
) -> Result<(), NmstateError> {
    let nm_devs = nm_api.devices_get().map_err(nm_error_to_nmstate)?;
    let nm_devs_indexed = create_index_for_nm_devs(&nm_devs);
    // Interfaces created by non-NM tools will not be deleted by connection
    // deletion, remove manually.
    for iface in merged_state
        .interfaces
        .kernel_ifaces
        .values()
        .filter(|i| {
            i.is_changed() && (i.merged.is_absent() || i.merged.is_down())
        })
        .map(|i| &i.merged)
    {
        if iface.is_virtual() {
            if let Some(nm_dev) = nm_devs_indexed.get(&(
                iface.name().to_string(),
                iface_type_to_nm(&iface.iface_type())?,
            )) {
                log::info!(
                    "Deleting interface {}/{}: {}",
                    &iface.name(),
                    &iface.iface_type(),
                    &nm_dev.obj_path
                );
                // There might be an race with on-going profile/connection
                // deletion, verification will raise error for it later.
                if let Err(e) = nm_api.device_delete(&nm_dev.obj_path) {
                    log::debug!("Failed to delete interface {:?}", e);
                }
            }
        }
    }
    Ok(())
}

// If any connection still referring to deleted UUID, we should delete it also
fn delete_orphan_ports(
    nm_api: &mut NmApi,
    uuids_deleted: &HashSet<&str>,
) -> Result<(), NmstateError> {
    let mut uuids_to_delete = Vec::new();
    let all_nm_conns = nm_api.connections_get().map_err(nm_error_to_nmstate)?;
    for nm_conn in &all_nm_conns {
        if nm_conn.iface_type() != Some(NM_SETTING_OVS_PORT_SETTING_NAME) {
            continue;
        }
        if let Some(ctrl_uuid) = nm_conn.controller() {
            if uuids_deleted.contains(ctrl_uuid) {
                if let Some(uuid) = nm_conn.uuid() {
                    log::info!(
                        "Deleting NM orphan profile {}/{}: {}",
                        nm_conn.iface_name().unwrap_or(""),
                        nm_conn.iface_type().unwrap_or(""),
                        uuid
                    );
                    uuids_to_delete.push(uuid);
                }
            }
        }
    }
    for uuid in &uuids_to_delete {
        nm_api
            .connection_delete(uuid)
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}

// * NM has problem on remove routes, we need to deactivate it first
//  https://bugzilla.redhat.com/1837254
// * NM cannot change VRF table ID, so we deactivate first
// * VLAN config changed.
// * Veth peer changed.
// * NM cannot reapply changes to MPTCP flags.
fn gen_nm_conn_need_to_deactivate_first(
    nm_conns_to_activate: &[NmConnection],
    activated_nm_conns: &[&NmConnection],
) -> Vec<NmConnection> {
    let mut ret: Vec<NmConnection> = Vec::new();
    for nm_conn in nm_conns_to_activate {
        if let Some(uuid) = nm_conn.uuid() {
            if let Some(activated_nm_con) =
                activated_nm_conns.iter().find(|c| {
                    if let Some(cur_uuid) = c.uuid() {
                        cur_uuid == uuid
                    } else {
                        false
                    }
                })
            {
                if is_route_removed(nm_conn, activated_nm_con)
                    || is_vrf_table_id_changed(nm_conn, activated_nm_con)
                    || is_vlan_changed(nm_conn, activated_nm_con)
                    || is_vxlan_changed(nm_conn, activated_nm_con)
                    || is_veth_peer_changed(nm_conn, activated_nm_con)
                    || is_mptcp_flags_changed(nm_conn, activated_nm_con)
                {
                    ret.push((*activated_nm_con).clone());
                }
            }
        }
    }
    ret
}
