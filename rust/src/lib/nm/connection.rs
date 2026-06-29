// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use super::{
    NmConnectionMatcher,
    device::create_index_for_nm_devs,
    nm_dbus::{NmConnection, NmDevice, NmIfaceType},
    settings::{fix_ip_dhcp_timeout, iface_to_nm_connections},
};
use crate::{
    InterfaceType, MergedInterface, MergedInterfaces, MergedNetworkState,
    NmstateError,
};

#[cfg_attr(not(feature = "query_apply"), allow(dead_code))]
pub(crate) struct PreparedNmConnections {
    pub(crate) to_store: Vec<NmConnection>,
    pub(crate) to_activate: Vec<NmConnection>,
    pub(crate) to_deactivate: Vec<NmDevice>,
    pub(crate) to_delete: Vec<String>,
}

pub(crate) fn prepare_nm_conns(
    merged_state: &MergedNetworkState,
    conn_matcher: &NmConnectionMatcher,
    nm_devs: &[NmDevice],
    gen_conf_mode: bool,
    is_retry: bool,
    forwarding_supported: bool,
) -> Result<PreparedNmConnections, NmstateError> {
    let mut nm_conns_to_update: Vec<NmConnection> = Vec::new();
    let mut nm_conns_to_activate: Vec<NmConnection> = Vec::new();

    let mut ifaces: Vec<&MergedInterface> = merged_state
        .interfaces
        .iter()
        .filter(|i| i.is_changed())
        .collect();

    ifaces.sort_unstable_by_key(|iface| iface.merged.name());
    // Use sort_by_key() instead of unstable one, do we can alphabet
    // activation order which is required to simulate the OS boot-up.
    ifaces.sort_by_key(|iface| {
        if let Some(i) = iface.for_apply.as_ref() {
            i.base_iface().up_priority
        } else {
            u32::MAX
        }
    });

    let nm_devs_indexed = create_index_for_nm_devs(nm_devs);
    let mut nm_devs_to_deactivate: Vec<NmDevice> = ifaces
        .iter()
        .filter(|iface| {
            iface.for_apply.as_ref().map(|i| i.is_down()) == Some(true)
                // Deactivating an OVS internal interface detaches it from the
                // bridge, destroying the local port. For state:down we keep it
                // attached with the link administratively down, matching the
                // behaviour of `ovs-vsctl add-br` (local port DOWN, no kernel
                // traffic). See NMT-2268.
                && iface.merged.iface_type() != InterfaceType::OvsInterface
        })
        .filter_map(|iface| {
            nm_devs_indexed
                .get(&(iface.merged.name(), iface.merged.iface_type()))
                .copied()
        })
        .cloned()
        .collect();

    for merged_iface in ifaces.iter().filter(|i| {
        i.merged.iface_type() != InterfaceType::Unknown && !i.merged.is_absent()
    }) {
        let iface = if let Some(i) = merged_iface.for_apply.as_ref() {
            i
        } else {
            continue;
        };

        for mut nm_conn in iface_to_nm_connections(
            merged_iface,
            merged_state,
            conn_matcher,
            gen_conf_mode,
        )? {
            // Clear forwarding when not supported by NetworkManager to prevent
            // failures. TODO: Remove this code once the minimum
            // supported NetworkManager version is >= 1.54
            if !forwarding_supported {
                if let Some(ipv4) = nm_conn.ipv4.as_mut() {
                    ipv4.forwarding = None;
                }

                if let Some(desired_iface) = merged_iface.desired.as_ref() {
                    let forwarding_desired = desired_iface
                        .base_iface()
                        .ipv4
                        .as_ref()
                        .and_then(|ip4| ip4.forwarding)
                        .is_some();

                    if forwarding_desired {
                        log::warn!(
                            "Clearing unsupported ipv4.forwarding for \
                             interface '{}'",
                            desired_iface.name()
                        );
                    }
                }
            }

            if iface.is_up()
                && (is_retry
                    || !can_skip_activation(
                        merged_iface,
                        &merged_state.interfaces,
                        &nm_conn,
                        conn_matcher,
                    ))
            {
                nm_conns_to_activate.push(nm_conn.clone());
            }
            // User try to bring a unmanaged interface down, we activate it and
            // deactivate it again.
            if iface.is_down()
                && merged_iface.current.as_ref().map(|i| i.is_ignore())
                    == Some(true)
            {
                nm_conns_to_activate.push(nm_conn.clone());
                if let Some(&nm_dev) =
                    nm_devs_indexed.get(&(iface.name(), iface.iface_type()))
                {
                    nm_devs_to_deactivate.push(nm_dev.clone());
                }
            }
            if iface.is_down()
                && gen_conf_mode
                && let Some(nm_conn_set) = nm_conn.connection.as_mut()
            {
                nm_conn_set.autoconnect = Some(false);
            }
            nm_conns_to_update.push(nm_conn);
        }
    }

    fix_ip_dhcp_timeout(&mut nm_conns_to_update);

    let mut ret = PreparedNmConnections {
        to_store: nm_conns_to_update,
        to_activate: nm_conns_to_activate,
        to_deactivate: nm_devs_to_deactivate,
        to_delete: Vec::new(),
    };

    // When port list is desired on controller interface, we need to update
    // saved NmConnection to prevent undesired port attached by
    // `auto-connect-ports: true`. Hence we use this Vec to track
    // port list desired ifaces.
    detach_saved_nm_conn_from_controller(
        &mut ret,
        &merged_state.interfaces,
        conn_matcher,
    );

    Ok(ret)
}

// When a new virtual interface is desired, if its controller is also newly
// created, in NetworkManager, there is no need to activate the subordinates.
fn can_skip_activation(
    merged_iface: &MergedInterface,
    merged_ifaces: &MergedInterfaces,
    nm_conn: &NmConnection,
    conn_matcher: &NmConnectionMatcher,
) -> bool {
    // if the controller is desired to be down or absent, activating the
    // connection on the port will risk making the controller activate again,
    // therefore skip the activation on the port
    if let Some(desired_iface) = merged_iface.for_apply.as_ref()
        && let (Some(ctrl_iface), Some(ctrl_type)) = (
            desired_iface.base_iface().controller.as_deref(),
            desired_iface.base_iface().controller_type.as_ref(),
        )
        && let Some(merged_ctrl_iface) =
            merged_ifaces.get_iface(ctrl_iface, ctrl_type.clone())
        && merged_ctrl_iface.for_apply.is_some()
        && (merged_ctrl_iface.merged.is_absent()
            || merged_ctrl_iface.merged.is_down())
    {
        log::info!(
            "Skipping activation of {} as its controller {} desire to be down \
             or absent",
            merged_iface.merged.name(),
            ctrl_iface
        );
        return true;
    }
    // Reapply of connection never reactivate its subordinates, hence we do not
    // skip activation when modifying the connection.
    if let Some(uuid) = nm_conn.uuid()
        && conn_matcher.is_activated(uuid)
    {
        return false;
    }

    if merged_iface.current.is_none()
        && merged_iface.for_apply.is_some()
        && merged_iface.merged.is_up()
        && let Some(desired_iface) = merged_iface.for_apply.as_ref()
    {
        if let (Some(ctrl_iface), Some(ctrl_type)) = (
            desired_iface.base_iface().controller.as_deref(),
            desired_iface.base_iface().controller_type.as_ref(),
        ) && let Some(merged_ctrl_iface) =
            merged_ifaces.get_iface(ctrl_iface, ctrl_type.clone())
            && merged_ctrl_iface.current.is_none()
            && merged_ctrl_iface.for_apply.is_some()
            && merged_ctrl_iface.merged.is_up()
        {
            log::info!(
                "Skipping activation of {} as its controller {} will \
                 automatically activate it",
                merged_iface.merged.name(),
                ctrl_iface
            );
            return true;
        }

        // new OVS port on new OVS bridge can skip activation
        if nm_conn.iface_type() == Some(&NmIfaceType::OvsPort) {
            return true;
        }
    }
    false
}

// If a controller has port list desired, detach saved inactive NmConnection
// from this controller
fn detach_saved_nm_conn_from_controller(
    prepared_conns: &mut PreparedNmConnections,
    merged_ifaces: &MergedInterfaces,
    conn_matcher: &NmConnectionMatcher,
) {
    // Only need to check inactive NmConnection because active NmConnection
    // is already processed by `MergedInterfaces::handle_changed_ports()`.
    let saved_inactive_port_nm_conn: Vec<&NmConnection> = conn_matcher
        .saved_iter()
        .filter(|nm_conn| {
            if let Some(uuid) = nm_conn.uuid() {
                !conn_matcher.is_uuid_activated(uuid)
                    && !is_prepared_to_store(prepared_conns, uuid)
                    && nm_conn.controller().is_some()
            } else {
                false
            }
        })
        .collect();

    if saved_inactive_port_nm_conn.is_empty() {
        return;
    }

    let mut changed_ctrl_names: HashSet<(&str, NmIfaceType)> = HashSet::new();
    let mut changed_ctrl_uuids: HashSet<(&str, NmIfaceType)> = HashSet::new();

    for merged_iface in merged_ifaces.iter().filter(|merged_iface| {
        is_ctrl_iface_desired_port_changes(merged_iface)
            && merged_iface.for_apply.as_ref().map(|i| i.is_up()) == Some(true)
    }) {
        let ctrl_iface_name = merged_iface.merged.name();
        let ctrl_iface_type = &merged_iface.merged.base_iface().iface_type;
        let ctrl_nm_iface_type = NmIfaceType::from(ctrl_iface_type);
        if let Some(ctrl_nm_conn) = prepared_conns
            .to_activate
            .as_slice()
            .iter()
            .find(|nm_conn| {
                nm_conn.iface_name() == Some(ctrl_iface_name)
                    && nm_conn.iface_type() == Some(&ctrl_nm_iface_type)
            })
            && let Some(uuid) = ctrl_nm_conn.uuid()
        {
            changed_ctrl_names.insert((ctrl_iface_name, ctrl_nm_iface_type));
            changed_ctrl_uuids.insert((uuid, ctrl_nm_iface_type));
        }
    }

    let mut orphan_ovs_port_uuids: HashSet<&str> = HashSet::new();
    let mut orphan_ovs_port_names: HashSet<&str> = HashSet::new();

    for nm_conn in saved_inactive_port_nm_conn.as_slice() {
        if let Some(ctrl_name) = nm_conn.controller()
            && let Some(nm_ctrl_type) = nm_conn.controller_type()
            && ((is_uuid(ctrl_name)
                && changed_ctrl_uuids.contains(&(ctrl_name, *nm_ctrl_type)))
                || changed_ctrl_names.contains(&(ctrl_name, *nm_ctrl_type)))
        {
            if nm_conn.iface_type() == Some(&NmIfaceType::OvsPort) {
                if let Some(uuid) = nm_conn.uuid() {
                    log::debug!("Deleting orphan OVS port {uuid}");
                    log::info!(
                        "Deleting connection {uuid}: {}/ovs-port",
                        nm_conn.iface_name().unwrap_or_default(),
                    );
                    prepared_conns.to_delete.push(uuid.to_string());
                    orphan_ovs_port_uuids.insert(uuid);
                    if let Some(ovs_port_iface_name) = nm_conn.iface_name() {
                        orphan_ovs_port_names.insert(ovs_port_iface_name);
                    }
                }
            } else {
                let mut changed_nm_conn = (*nm_conn).clone();
                if let Some(nm_conn_set) = changed_nm_conn.connection.as_mut() {
                    log::debug!(
                        "Detaching inactive controller port {}: {}/{}",
                        nm_conn.uuid().unwrap_or_default(),
                        nm_conn.iface_name().unwrap_or_default(),
                        nm_conn.iface_type().unwrap_or(&NmIfaceType::Unknown)
                    );
                    nm_conn_set.controller = None;
                    nm_conn_set.controller_type = None;
                    changed_nm_conn.bond_port = None;
                    changed_nm_conn.bridge_port = None;
                    prepared_conns.to_store.push(changed_nm_conn);
                }
            }
        }
    }

    // Detach OVS system and internal interface which refer to orphan OVS ports
    for nm_conn in saved_inactive_port_nm_conn {
        if nm_conn.controller_type() == Some(&NmIfaceType::OvsPort)
            && let Some(ctrl_name) = nm_conn.controller()
            && (is_uuid(ctrl_name)
                && orphan_ovs_port_uuids.contains(&ctrl_name)
                || orphan_ovs_port_names.contains(&ctrl_name))
        {
            // OVS internal interface cannot live without its parent
            if nm_conn.iface_type() == Some(&NmIfaceType::OvsIface) {
                if let Some(uuid) = nm_conn.uuid() {
                    prepared_conns.to_delete.push(uuid.to_string());
                }
            } else {
                let mut changed_nm_conn = nm_conn.clone();
                if let Some(nm_conn_set) = changed_nm_conn.connection.as_mut() {
                    log::debug!(
                        "Detaching inactive OVS interface {}: {}/{}",
                        nm_conn.uuid().unwrap_or_default(),
                        nm_conn.iface_name().unwrap_or_default(),
                        nm_conn.iface_type().unwrap_or(&NmIfaceType::Unknown)
                    );
                    nm_conn_set.controller = None;
                    nm_conn_set.controller_type = None;
                    changed_nm_conn.ovs_iface = None;
                    prepared_conns.to_store.push(changed_nm_conn);
                }
            }
        }
    }
}

fn is_prepared_to_store(
    prepared_conns: &PreparedNmConnections,
    uuid: &str,
) -> bool {
    prepared_conns
        .to_store
        .as_slice()
        .iter()
        .any(|nm_conn| nm_conn.uuid() == Some(uuid))
}

fn is_ctrl_iface_desired_port_changes(merged_iface: &MergedInterface) -> bool {
    merged_iface.for_apply.as_ref().map(|i| i.ports().is_some()) == Some(true)
}

pub(crate) fn is_uuid(value: &str) -> bool {
    uuid::Uuid::parse_str(value).is_ok()
}
