// SPDX-License-Identifier: Apache-2.0

use super::{
    nm_dbus::{NmConnection, NmIfaceType},
    settings::{fix_ip_dhcp_timeout, iface_to_nm_connections},
    NmConnectionMatcher,
};

use crate::{
    InterfaceType, MergedInterface, MergedInterfaces, MergedNetworkState,
    NmstateError,
};

#[cfg_attr(not(feature = "query_apply"), allow(dead_code))]
pub(crate) struct PerparedNmConnections {
    pub(crate) to_store: Vec<NmConnection>,
    pub(crate) to_activate: Vec<NmConnection>,
    pub(crate) to_deactivate: Vec<NmConnection>,
}

pub(crate) fn perpare_nm_conns(
    merged_state: &MergedNetworkState,
    conn_matcher: &NmConnectionMatcher,
    gen_conf_mode: bool,
    is_retry: bool,
    forwarding_supported: bool,
) -> Result<PerparedNmConnections, NmstateError> {
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

    let mut nm_conns_to_deactivate: Vec<NmConnection> = ifaces
        .as_slice()
        .iter()
        .filter(|iface| iface.merged.is_down())
        .filter_map(|iface| conn_matcher.get_applied(iface.merged.base_iface()))
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
                            "Clearing ipv4.forwarding for interface '{}': \
                             NetworkManager is too old to support this feature",
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
                nm_conns_to_deactivate.push(nm_conn.clone());
            }
            if iface.is_down() && gen_conf_mode {
                if let Some(nm_conn_set) = nm_conn.connection.as_mut() {
                    nm_conn_set.autoconnect = Some(false);
                }
            }
            nm_conns_to_update.push(nm_conn);
        }
    }

    fix_ip_dhcp_timeout(&mut nm_conns_to_update);

    Ok(PerparedNmConnections {
        to_store: nm_conns_to_update,
        to_activate: nm_conns_to_activate,
        to_deactivate: nm_conns_to_deactivate,
    })
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
    if let Some(desired_iface) = merged_iface.for_apply.as_ref() {
        if let (Some(ctrl_iface), Some(ctrl_type)) = (
            desired_iface.base_iface().controller.as_deref(),
            desired_iface.base_iface().controller_type.as_ref(),
        ) {
            if let Some(merged_ctrl_iface) =
                merged_ifaces.get_iface(ctrl_iface, ctrl_type.clone())
            {
                if merged_ctrl_iface.for_apply.is_some()
                    && (merged_ctrl_iface.merged.is_absent()
                        || merged_ctrl_iface.merged.is_down())
                {
                    log::info!(
                        "Skipping activation of {} as its controller {} \
                         desire to be down or absent",
                        merged_iface.merged.name(),
                        ctrl_iface
                    );
                    return true;
                }
            }
        }
    }
    // Reapply of connection never reactivate its subordinates, hence we do not
    // skip activation when modifying the connection.
    if let Some(uuid) = nm_conn.uuid() {
        if conn_matcher.is_activated(uuid) {
            return false;
        }
    }

    if merged_iface.current.is_none()
        && merged_iface.for_apply.is_some()
        && merged_iface.merged.is_up()
    {
        if let Some(desired_iface) = merged_iface.for_apply.as_ref() {
            if let (Some(ctrl_iface), Some(ctrl_type)) = (
                desired_iface.base_iface().controller.as_deref(),
                desired_iface.base_iface().controller_type.as_ref(),
            ) {
                if let Some(merged_ctrl_iface) =
                    merged_ifaces.get_iface(ctrl_iface, ctrl_type.clone())
                {
                    if merged_ctrl_iface.current.is_none()
                        && merged_ctrl_iface.for_apply.is_some()
                        && merged_ctrl_iface.merged.is_up()
                    {
                        log::info!(
                            "Skipping activation of {} as its controller {} \
                             will automatically activate it",
                            merged_iface.merged.name(),
                            ctrl_iface
                        );
                        return true;
                    }
                }
            }

            // new OVS port on new OVS bridge can skip activation
            if nm_conn.iface_type() == Some(&NmIfaceType::OvsPort) {
                return true;
            }
        }
    }
    false
}
