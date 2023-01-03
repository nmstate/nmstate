// SPDX-License-Identifier: Apache-2.0

use super::super::{
    nm_dbus::NmConnection,
    settings::{get_exist_profile, NM_SETTING_OVS_PORT_SETTING_NAME},
};

use crate::{Interface, InterfaceType, Interfaces};

// When OVS system interface got detached from OVS bridge, we should remove its
// ovs port also.
pub(crate) fn get_orphan_ovs_port_uuids<'a>(
    ifaces: &Interfaces,
    cur_ifaces: &Interfaces,
    exist_nm_conns: &'a [NmConnection],
) -> Vec<&'a str> {
    let mut ret = Vec::new();
    for iface in ifaces.kernel_ifaces.values().filter(|i| {
        i.base_iface().controller_type.is_some()
            && i.base_iface().controller_type.as_ref()
                != Some(&InterfaceType::OvsBridge)
            && iface_was_ovs_sys_iface(i, cur_ifaces)
    }) {
        if let Some(exist_profile) = get_exist_profile(
            exist_nm_conns,
            iface.name(),
            &iface.iface_type(),
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
                    // We only touch port profiles created by nmstate which is
                    // using UUID for parent reference.
                    if uuid::Uuid::parse_str(parent).is_ok() {
                        log::info!(
                            "Deleting orphan OVS port connection {} \
                            as interface {}({}) detached from OVS bridge",
                            parent,
                            iface.name(),
                            iface.iface_type()
                        );
                        ret.push(parent.as_str())
                    }
                }
            }
        }
    }
    ret
}

fn iface_was_ovs_sys_iface(iface: &Interface, cur_ifaces: &Interfaces) -> bool {
    cur_ifaces.kernel_ifaces.get(iface.name()).map(|i| {
        i.base_iface().controller_type == Some(InterfaceType::OvsBridge)
    }) == Some(true)
}
