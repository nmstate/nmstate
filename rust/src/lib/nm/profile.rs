// SPDX-License-Identifier: Apache-2.0

use super::nm_dbus::{NmActiveConnection, NmConnection};
use super::settings::{
    get_exist_profile, iface_to_nm_connections, remove_nm_mptcp_set,
    use_uuid_for_controller_reference, use_uuid_for_parent_reference,
};

use crate::{
    InterfaceType, MergedInterface, MergedInterfaces, MergedNetworkState,
    NmstateError,
};

#[allow(dead_code)]
pub(crate) struct PerparedNmConnections {
    pub(crate) to_store: Vec<NmConnection>,
    pub(crate) to_activate: Vec<NmConnection>,
    pub(crate) to_deactivate: Vec<NmConnection>,
}

pub(crate) fn perpare_nm_conns(
    merged_state: &MergedNetworkState,
    exist_nm_conns: &[NmConnection],
    nm_acs: &[NmActiveConnection],
    mptcp_supported: bool,
    gen_conf_mode: bool,
) -> Result<PerparedNmConnections, NmstateError> {
    let mut nm_conns_to_update: Vec<NmConnection> = Vec::new();
    let mut nm_conns_to_activate: Vec<NmConnection> = Vec::new();

    let nm_ac_uuids: Vec<&str> =
        nm_acs.iter().map(|nm_ac| &nm_ac.uuid as &str).collect();

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
        .filter_map(|iface| {
            get_exist_profile(
                exist_nm_conns,
                &iface.merged.base_iface().name,
                &iface.merged.base_iface().iface_type,
                &nm_ac_uuids,
            )
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
            exist_nm_conns,
            &nm_ac_uuids,
            gen_conf_mode,
        )? {
            if !mptcp_supported {
                remove_nm_mptcp_set(&mut nm_conn);
                if let Some(mptcp_conf) = iface.base_iface().mptcp.as_ref() {
                    log::warn!(
                        "MPTCP not supported by NetworkManager, \
                        Ignoring MPTCP config {:?}",
                        mptcp_conf
                    );
                }
            }

            if iface.is_up()
                && !can_skip_activation(
                    merged_iface,
                    &merged_state.interfaces,
                    &nm_conn,
                    exist_nm_conns,
                )
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

    use_uuid_for_controller_reference(
        &mut nm_conns_to_update,
        &merged_state.interfaces,
        exist_nm_conns,
    )?;

    use_uuid_for_parent_reference(
        &mut nm_conns_to_update,
        &merged_state.interfaces,
        exist_nm_conns,
    );

    Ok(PerparedNmConnections {
        to_store: nm_conns_to_update,
        to_activate: nm_conns_to_activate,
        to_deactivate: nm_conns_to_deactivate,
    })
}

// When a new virtual interface is desired, if its controller is also newly
// created, in NetworkManager, there is no need to activate the subordinates.
// For OVS stuff, always return false.
fn can_skip_activation(
    merged_iface: &MergedInterface,
    merged_ifaces: &MergedInterfaces,
    nm_conn: &NmConnection,
    exist_nm_conns: &[NmConnection],
) -> bool {
    // Reapply of connection never reactivate its subordinates, hence we do not
    // skip activation when modifying the connection.
    if let Some(uuid) = nm_conn.uuid() {
        if exist_nm_conns.iter().any(|c| c.uuid() == Some(uuid)) {
            return false;
        }
    }

    if merged_iface.current.is_none()
        && merged_iface.for_apply.is_some()
        && merged_iface.merged.is_up()
        && merged_iface.merged.iface_type() != InterfaceType::OvsInterface
    {
        if let Some(desired_iface) = merged_iface.for_apply.as_ref() {
            if let (Some(ctrl_iface), Some(ctrl_type)) = (
                desired_iface.base_iface().controller.as_deref(),
                desired_iface.base_iface().controller_type.as_ref(),
            ) {
                if ctrl_type == &InterfaceType::OvsBridge {
                    return false;
                }
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
        }
    }
    false
}
