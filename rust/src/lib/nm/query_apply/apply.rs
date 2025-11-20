// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use super::super::{
    connection::{prepare_nm_conns, PreparedNmConnections},
    device::create_index_for_nm_devs,
    error::nm_error_to_nmstate,
    nm_dbus::{NmApi, NmConnection, NmIfaceType, NmVersion, NmVersionInfo},
    query_apply::{
        activate_nm_connections, connection::is_uuid,
        deactivate_nm_connections, deactivate_nm_devices,
        delete_exist_connections, delete_orphan_ovs_ports,
        dispatch::apply_dispatch_script, dns::store_dns_config, is_hsr_changed,
        is_ipvlan_changed, is_mptcp_flags_changed, is_route_removed,
        is_veth_peer_changed, is_vlan_changed, is_vrf_table_id_changed,
        is_vxlan_changed, save_nm_connections,
    },
    route::store_route_config,
    route_rule::store_route_rule_config,
    NmConnectionMatcher,
};

use crate::{
    InterfaceType, MergedInterfaces, MergedNetworkState, NmstateError,
};

// There is plan to simply the `add_net_state`, `chg_net_state`, `del_net_state`
// `cur_net_state`, `des_net_state` into single struct. Suppress the clippy
// warning for now
pub(crate) async fn nm_apply(
    merged_state: &MergedNetworkState,
    checkpoint: &str,
    timeout: u32,
    is_retry: bool,
) -> Result<(), NmstateError> {
    let mut nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    let mut nm_route_remove_needs_deactivate = true;
    let mut ipv4_forward_support = false;

    check_nm_version(
        &nm_api,
        &mut nm_route_remove_needs_deactivate,
        &mut ipv4_forward_support,
    )
    .await;

    nm_api.set_checkpoint(checkpoint, timeout);
    nm_api.set_checkpoint_auto_refresh(true);

    apply_dispatch_script(&merged_state.interfaces)?;

    if !merged_state.memory_only {
        delete_ifaces(&mut nm_api, merged_state).await?;
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
            nm_api
                .hostname_set(hostname)
                .await
                .map_err(nm_error_to_nmstate)?;
        }
    }

    let nm_saved_conns = nm_api
        .connections_get()
        .await
        .map_err(nm_error_to_nmstate)?;
    let nm_acs = nm_api
        .active_connections_get()
        .await
        .map_err(nm_error_to_nmstate)?;
    let nm_applied_conns = nm_api
        .applied_connections_get()
        .await
        .map_err(nm_error_to_nmstate)?;

    let conn_matcher = NmConnectionMatcher::new(
        nm_saved_conns,
        nm_applied_conns,
        nm_acs.clone(),
        &merged_state.interfaces,
    );

    let nm_devs = nm_api.devices_get().await.map_err(nm_error_to_nmstate)?;

    let mut merged_state = merged_state.clone();

    store_route_config(&mut merged_state)?;

    store_route_rule_config(&mut merged_state)?;

    store_dns_config(&mut merged_state, &mut nm_api, &nm_acs, &nm_devs).await?;

    let PreparedNmConnections {
        to_store: nm_conns_to_store,
        to_activate: nm_conns_to_activate,
        to_deactivate: nm_devs_to_deactivate,
    } = prepare_nm_conns(
        &merged_state,
        &conn_matcher,
        &nm_devs,
        false,
        is_retry,
        ipv4_forward_support,
    )?;

    let nm_conns_to_deactivate_first = gen_nm_conn_need_to_deactivate_first(
        &merged_state.interfaces,
        nm_conns_to_activate.as_slice(),
        &conn_matcher,
        nm_route_remove_needs_deactivate,
    );
    deactivate_nm_connections(
        &mut nm_api,
        nm_conns_to_deactivate_first.as_slice(),
    )
    .await?;

    save_nm_connections(
        &mut nm_api,
        nm_conns_to_store.as_slice(),
        merged_state.memory_only,
    )
    .await?;
    if !merged_state.memory_only {
        delete_exist_connections(
            &mut nm_api,
            &merged_state,
            &conn_matcher,
            &nm_conns_to_store,
        )
        .await?;
        delete_orphan_ovs_ports(
            &mut nm_api,
            &merged_state.interfaces,
            &conn_matcher,
            &nm_conns_to_activate,
        )
        .await?;
    }

    activate_nm_connections(
        &mut nm_api,
        nm_conns_to_activate.as_slice(),
        &conn_matcher,
    )
    .await?;

    // Deactivate the devices, not their connections. According to NM's
    // documentation, this prevents automatic connection activations.
    // We have deleted most of the other matching connections, but we cannot
    // delete some connections with "multiconnect". This would lead to unwanted
    // connection activations if we use deactivate_nm_connections.
    deactivate_nm_devices(&mut nm_api, &nm_devs_to_deactivate).await?;

    Ok(())
}

async fn delete_ifaces(
    nm_api: &mut NmApi<'_>,
    merged_state: &MergedNetworkState,
) -> Result<(), NmstateError> {
    let all_saved_nm_conns = nm_api
        .connections_get()
        .await
        .map_err(nm_error_to_nmstate)?;

    let conn_matcher = NmConnectionMatcher::new(
        all_saved_nm_conns,
        Vec::new(),
        Vec::new(),
        &merged_state.interfaces,
    );

    let mut uuids_to_delete: HashSet<&str> = HashSet::new();

    for merged_iface in merged_state
        .interfaces
        .iter()
        .filter(|i| i.is_changed() && i.merged.is_absent())
    {
        let iface = &merged_iface.merged;

        let nm_conns_to_delete = conn_matcher.get_saved(iface.base_iface());

        // Delete all existing connections for this interface
        for nm_conn in nm_conns_to_delete {
            if let Some(uuid) = nm_conn.uuid() {
                if !uuids_to_delete.contains(uuid) {
                    log::info!(
                        "Deleting NM connection for absent interface {}/{}: {}",
                        &iface.name(),
                        &iface.iface_type(),
                        uuid
                    );
                    uuids_to_delete.insert(uuid);
                }
            }
            // Delete OVS port profile along with OVS system and internal
            // Interface
            if nm_conn.controller_type() == Some(&NmIfaceType::OvsPort) {
                if let Some(ctrl) = nm_conn.controller() {
                    if is_uuid(ctrl) {
                        if !uuids_to_delete.contains(ctrl) {
                            log::info!(
                                "Deleting NM OVS port connection {} for \
                                 absent OVS interface {}",
                                ctrl,
                                &iface.name(),
                            );
                            uuids_to_delete.insert(ctrl);
                        }
                    } else {
                        let nm_conns = conn_matcher.get_saved_by_name_type(
                            ctrl,
                            &NmIfaceType::OvsPort,
                        );
                        for nm_conn in nm_conns {
                            if let Some(uuid) = nm_conn.uuid() {
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
            }
        }
    }

    for uuid in &uuids_to_delete {
        nm_api
            .connection_delete(uuid)
            .await
            .map_err(nm_error_to_nmstate)?;
    }

    delete_orphan_ports(nm_api, &uuids_to_delete).await?;
    delete_remain_virtual_interface_as_desired(nm_api, merged_state).await?;
    Ok(())
}

async fn delete_remain_virtual_interface_as_desired(
    nm_api: &mut NmApi<'_>,
    merged_state: &MergedNetworkState,
) -> Result<(), NmstateError> {
    let nm_devs = nm_api.devices_get().await.map_err(nm_error_to_nmstate)?;
    let nm_devs_indexed = create_index_for_nm_devs(&nm_devs);
    // Interfaces created by non-NM tools will not be deleted by connection
    // deletion, remove manually.
    for iface in merged_state
        .interfaces
        .kernel_ifaces
        .values()
        .filter(|i| {
            i.merged.iface_type() != InterfaceType::OvsInterface
                && i.is_changed()
                && (i.merged.is_absent() || i.merged.is_down())
        })
        .map(|i| &i.merged)
    {
        if iface.is_virtual() {
            if let Some(nm_dev) =
                nm_devs_indexed.get(&(iface.name(), iface.iface_type()))
            {
                log::info!(
                    "Deleting interface {}/{}: {}",
                    &iface.name(),
                    &iface.iface_type(),
                    &nm_dev.obj_path
                );
                // There might be an race with on-going profile/connection
                // deletion, verification will raise error for it later.
                if let Err(e) = nm_api.device_delete(&nm_dev.obj_path).await {
                    log::debug!("Failed to delete interface {e:?}");
                }
            }
        }
    }
    Ok(())
}

// If any connection still referring to deleted UUID, we should delete it also
async fn delete_orphan_ports(
    nm_api: &mut NmApi<'_>,
    uuids_deleted: &HashSet<&str>,
) -> Result<(), NmstateError> {
    let mut uuids_to_delete: Vec<&str> = Vec::new();
    let all_nm_conns = nm_api
        .connections_get()
        .await
        .map_err(nm_error_to_nmstate)?;
    for nm_conn in &all_nm_conns {
        if nm_conn.iface_type() != Some(&NmIfaceType::OvsPort) {
            continue;
        }
        if let Some(ctrl_uuid) = nm_conn.controller() {
            if uuids_deleted.contains(ctrl_uuid) {
                if let Some(uuid) = nm_conn.uuid() {
                    log::info!(
                        "Deleting NM orphan profile {}/{}: {}",
                        nm_conn.iface_name().unwrap_or(""),
                        nm_conn.iface_type().cloned().unwrap_or_default(),
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
            .await
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}

// * NM < 1.52 had problem on remove routes, we needed to deactivate it first.
//  On patched NM, we can just reapply.
//  https://bugzilla.redhat.com/1837254
//  https://issues.redhat.com/browse/RHEL-66262
//  https://issues.redhat.com/browse/RHEL-67324
// * NM cannot change VRF table ID, so we deactivate first
// * VLAN config changed.
// * Veth peer changed.
// * HSR config changed.
// * NM cannot reapply changes to MPTCP flags.
// * All VPN connection
// * All linux bridge ports should be deactivate if its controller has
//   default-pvid changes:
//      https://issues.redhat.com/browse/RHEL-26750
fn gen_nm_conn_need_to_deactivate_first(
    merged_iface: &MergedInterfaces,
    nm_conns_to_activate: &[NmConnection],
    conn_matcher: &NmConnectionMatcher,
    remove_routes_need_deactivate: bool,
) -> Vec<NmConnection> {
    let mut ret: Vec<NmConnection> = Vec::new();

    let default_pvid_changed_brs: Vec<&str> =
        get_default_pvid_changed_brs(merged_iface);
    let bond_queue_id_changed_ports =
        get_bond_ports_with_queue_id_changed(merged_iface);

    for nm_conn in nm_conns_to_activate {
        if let Some(uuid) = nm_conn.uuid() {
            // VPN connection does not have applied NmConnection
            if nm_conn.iface_type() == Some(&NmIfaceType::Vpn)
                && conn_matcher.is_uuid_activated(uuid)
            {
                ret.push(nm_conn.clone());
            } else if let Some(nm_applied_conn) =
                conn_matcher.get_applied_by_uuid(uuid)
            {
                if (remove_routes_need_deactivate
                    && is_route_removed(nm_conn, nm_applied_conn))
                    || is_vrf_table_id_changed(nm_conn, nm_applied_conn)
                    || is_vlan_changed(nm_conn, nm_applied_conn)
                    || is_hsr_changed(nm_conn, nm_applied_conn)
                    || is_vxlan_changed(nm_conn, nm_applied_conn)
                    || is_veth_peer_changed(nm_conn, nm_applied_conn)
                    || is_mptcp_flags_changed(nm_conn, nm_applied_conn)
                    || is_bridge_port_changed_default_pvid(
                        nm_conn,
                        &default_pvid_changed_brs,
                    )
                    || is_bond_port_queue_id_changed(
                        nm_conn,
                        &bond_queue_id_changed_ports,
                    )
                    || is_ipvlan_changed(nm_conn, nm_applied_conn)
                {
                    ret.push((*nm_applied_conn).clone());
                }
            }
        }
    }
    ret
}

async fn check_nm_version(
    nm_api: &NmApi<'_>,
    route_remove_needs_deactivate: &mut bool,
    ipv4_forward_support: &mut bool,
) {
    let version = if let Ok(ver_info) = nm_api.version_info().await {
        *route_remove_needs_deactivate = !ver_info
            .has_capability(NmVersionInfo::CAPABILITY_SYNC_ROUTE_WITH_TABLE);
        *ipv4_forward_support =
            ver_info.has_capability(NmVersionInfo::CAPABILITY_IP4_FORWARDING);
        Ok(ver_info.version())
    } else {
        // VersionInfo was added to NM 1.42. For older version we fallback to
        // parsing from Version string if VersionInfo is not available.
        *route_remove_needs_deactivate = true;
        *ipv4_forward_support = false;
        nm_api.version().await
    };

    let min = NmVersion::new(1, 46, 0);
    if let Ok(version) = version {
        if version < min {
            log::warn!(
                "Unsupported NetworkManager version {version}, expecting >= \
                 {min}"
            );
        }
    } else {
        log::warn!("Unknown NetworkManager version, expecting >= {min}");
    }
}

fn get_default_pvid_changed_brs(merged_iface: &MergedInterfaces) -> Vec<&str> {
    merged_iface
        .kernel_ifaces
        .values()
        .filter_map(|i| {
            if i.is_default_pvid_changed() {
                Some(i.merged.name())
            } else {
                None
            }
        })
        .collect()
}

fn is_bridge_port_changed_default_pvid(
    nm_conn: &NmConnection,
    default_pvid_changed_brs: &[&str],
) -> bool {
    if nm_conn.controller_type() == Some(&NmIfaceType::Bridge) {
        if let Some(ctrl_name) = nm_conn.controller() {
            if default_pvid_changed_brs.contains(&ctrl_name) {
                log::info!(
                    "Reactivating linux bridge port as its controller has \
                     `vlan-default-pvid` changes"
                );
                return true;
            }
        }
    }
    false
}

fn get_bond_ports_with_queue_id_changed(
    merged_iface: &MergedInterfaces,
) -> Vec<&str> {
    let mut ret = Vec::new();
    for iface in merged_iface.kernel_ifaces.values().filter(|i| {
        (i.is_desired() || i.is_changed())
            && i.merged.iface_type() == InterfaceType::Bond
    }) {
        ret.extend(iface.get_bond_ports_with_queue_id_changed());
    }
    ret
}

fn is_bond_port_queue_id_changed(
    nm_conn: &NmConnection,
    changed_ports: &[&str],
) -> bool {
    if nm_conn.controller_type() == Some(&NmIfaceType::Bond) {
        if let Some(iface_name) = nm_conn.iface_name() {
            if changed_ports.contains(&iface_name) {
                log::info!(
                    "Reactivating bond port {iface_name} as its queue ID has \
                     changed"
                );
                return true;
            }
        }
    }
    false
}
