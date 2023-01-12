// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{NmApi, NmConnection};
use super::super::{
    query_apply::profile::delete_profiles,
    settings::{get_exist_profile, NM_SETTING_OVS_PORT_SETTING_NAME},
};

use crate::{InterfaceType, MergedInterface, MergedInterfaces, NmstateError};

// When OVS system interface got detached from OVS bridge, we should remove its
// ovs port also.
pub(crate) fn delete_orphan_ovs_ports(
    nm_api: &mut NmApi,
    merged_ifaces: &MergedInterfaces,
    exist_nm_conns: &[NmConnection],
    nm_conns_to_activate: &[NmConnection],
) -> Result<(), NmstateError> {
    let mut orphans: Vec<&str> = Vec::new();
    for iface in merged_ifaces
        .kernel_ifaces
        .values()
        .filter(|i| i.is_changed())
    {
        if iface
            .for_apply
            .as_ref()
            .and_then(|i| i.base_iface().controller_type.as_ref())
            != Some(&InterfaceType::OvsBridge)
            && iface_was_ovs_sys_iface(iface)
        {
            if let Some(exist_profile) = get_exist_profile(
                exist_nm_conns,
                iface.merged.name(),
                &iface.merged.iface_type(),
                &Vec::new(),
            ) {
                if exist_profile
                    .connection
                    .as_ref()
                    .and_then(|c| c.controller_type.as_ref())
                    == Some(&NM_SETTING_OVS_PORT_SETTING_NAME.to_string())
                {
                    if let Some(parent) = exist_profile
                        .connection
                        .as_ref()
                        .and_then(|c| c.controller.as_ref())
                    {
                        // We only touch port profiles created by nmstate which
                        // is using UUID for parent reference.
                        if uuid::Uuid::parse_str(parent).is_ok() {
                            // The OVS bond might still have ports even
                            // specified interface detached, this OVS bond will
                            // be included in `nm_conns_to_activate()`, we just
                            // do not remove connection pending for activation.
                            if nm_conns_to_activate
                                .iter()
                                .any(|nm_conn| nm_conn.uuid() == Some(parent))
                            {
                                continue;
                            }

                            log::info!(
                                "Deleting orphan OVS port connection {parent} \
                                as interface {}({}) detached from OVS bridge",
                                iface.merged.name(),
                                iface.merged.iface_type()
                            );
                            orphans.push(parent)
                        }
                    }
                }
            }
        }
    }
    delete_profiles(nm_api, orphans.as_slice())
}

fn iface_was_ovs_sys_iface(iface: &MergedInterface) -> bool {
    iface
        .current
        .as_ref()
        .and_then(|i| i.base_iface().controller_type.as_ref())
        == Some(&InterfaceType::OvsBridge)
}
