// SPDX-License-Identifier: Apache-2.0

use super::nm_dbus::{NmConnection, NmIfaceType};
use super::{settings::fix_ip_dhcp_timeout, settings::iface_to_nm_profiles};

use crate::{
    InterfaceType, MergedInterface, MergedInterfaces, MergedNetworkState,
    NmstateError,
};

#[derive(Debug, Clone, PartialEq, Default)]
pub(crate) struct NmProfile {
    pub(crate) merged_iface: MergedInterface,
    pub(crate) conn: NmConnection,
    pub(crate) exist_conn: Option<NmConnection>,
    pub(crate) is_activated: bool,
    /// NM connection need to be deactivated before activation
    pub(crate) need_deactivation: bool,
    /// NM connection will be auto activated by its controller, hence
    /// no need to activate it in the first round. Will try normal activation
    /// in follow up retry
    pub(crate) skip_first_activation: bool,
    /// NM connection need to be activated even its iface is in down state
    pub(crate) need_activation: bool,
}

pub(crate) fn perpare_nm_profiles(
    merged_state: &MergedNetworkState,
    exist_nm_conns: &[NmConnection],
    nm_ac_uuids: &[&str],
    gen_conf_mode: bool,
) -> Result<Vec<NmProfile>, NmstateError> {
    let mut ret: Vec<NmProfile> = Vec::new();

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

    for merged_iface in ifaces.as_slice() {
        let iface = if let Some(i) = merged_iface.for_apply.as_ref() {
            i
        } else {
            continue;
        };

        if iface.is_absent() || iface.iface_type() == InterfaceType::Unknown {
            continue;
        }

        for mut nm_profile in iface_to_nm_profiles(
            merged_iface,
            merged_state,
            exist_nm_conns,
            nm_ac_uuids,
            gen_conf_mode,
        )? {
            if iface.is_up()
                && can_skip_first_activation(
                    &nm_profile,
                    &merged_state.interfaces,
                )
            {
                nm_profile.skip_first_activation = true;
            }
            if iface.is_down() {
                // User try to bring a unmanaged interface down, we activate it
                // and deactivate it again.
                if merged_iface.current.as_ref().map(|i| i.is_ignore())
                    == Some(true)
                {
                    nm_profile.need_activation = true;
                }
                if gen_conf_mode {
                    if let Some(nm_conn_set) =
                        nm_profile.conn.connection.as_mut()
                    {
                        nm_conn_set.autoconnect = Some(false);
                    }
                }
            }
            ret.push(nm_profile);
        }
    }

    fix_ip_dhcp_timeout(&mut ret);

    Ok(ret)
}

// When a new virtual interface is desired, if its controller is also newly
// created, in NetworkManager, there is no need to activate the subordinates.
fn can_skip_first_activation(
    nm_profile: &NmProfile,
    merged_ifaces: &MergedInterfaces,
) -> bool {
    let merged_iface = &nm_profile.merged_iface;
    let nm_con = &nm_profile.conn;
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
    if nm_profile.exist_conn.is_some() {
        return false;
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
            if nm_con.iface_type() == Some(&NmIfaceType::OvsPort) {
                return true;
            }
        }
    }
    false
}
