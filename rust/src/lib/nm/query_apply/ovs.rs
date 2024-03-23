// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{NmApi, NmConnection, NmDevice};
use super::super::{
    query_apply::profile::{delete_profiles, is_uuid},
    settings::{get_exist_profile, NM_SETTING_OVS_PORT_SETTING_NAME},
    show::nm_conn_to_base_iface,
};

use crate::{
    Interface, InterfaceType, MergedInterface, MergedInterfaces, NetworkState,
    NmstateError,
};

// When OVS system interface got detached from OVS bridge, we should remove its
// ovs port also.
pub(crate) fn delete_orphan_ovs_ports(
    nm_api: &mut NmApi,
    merged_ifaces: &MergedInterfaces,
    exist_nm_conns: &[NmConnection],
    nm_conns_to_activate: &[NmConnection],
) -> Result<(), NmstateError> {
    let mut orphan_ovs_port_uuids: Vec<&str> = Vec::new();
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
                    if let Some(ovs_port_name) = exist_profile
                        .connection
                        .as_ref()
                        .and_then(|c| c.controller.as_ref())
                    {
                        let ovs_port_uuid = if is_uuid(ovs_port_name) {
                            ovs_port_name
                        } else if let Some(uuid) = get_exist_profile(
                            exist_nm_conns,
                            ovs_port_name,
                            &InterfaceType::Other("ovs-port".to_string()),
                            &[],
                        )
                        .and_then(|c| c.uuid())
                        {
                            uuid
                        } else {
                            continue;
                        };
                        // The OVS bond might still have ports even
                        // specified interface detached, this OVS bond will
                        // be included in `nm_conns_to_activate()`, we just
                        // do not remove connection pending for activation.
                        if nm_conns_to_activate.iter().any(|nm_conn| {
                            nm_conn.uuid() == Some(ovs_port_uuid)
                        }) {
                            continue;
                        }

                        log::info!(
                            "Deleting orphan OVS port connection {} \
                            as interface {}({}) detached from OVS bridge",
                            ovs_port_uuid,
                            iface.merged.name(),
                            iface.merged.iface_type()
                        );
                        orphan_ovs_port_uuids.push(ovs_port_uuid)
                    }
                }
            }
        }
    }
    delete_profiles(nm_api, orphan_ovs_port_uuids.as_slice())
}

fn iface_was_ovs_sys_iface(iface: &MergedInterface) -> bool {
    iface
        .current
        .as_ref()
        .and_then(|i| i.base_iface().controller_type.as_ref())
        == Some(&InterfaceType::OvsBridge)
}

pub(crate) fn merge_ovs_netdev_tun_iface(
    net_state: &mut NetworkState,
    nm_devs: &[NmDevice],
    nm_conns: &[NmConnection],
) {
    let tun_nm_devs: Vec<&NmDevice> = nm_devs
        .iter()
        .filter(|d| d.iface_type.as_str() == "tun")
        .collect();
    let tun_nm_conns: Vec<&NmConnection> = nm_conns
        .iter()
        .filter(|c| c.iface_type() == Some("tun"))
        .collect();
    for iface in net_state
        .interfaces
        .kernel_ifaces
        .values_mut()
        .filter(|i| i.iface_type() == InterfaceType::OvsInterface)
    {
        if let (Some(nm_dev), Some(nm_conn)) = (
            tun_nm_devs
                .as_slice()
                .iter()
                .find(|d| d.name.as_str() == iface.name()),
            tun_nm_conns
                .as_slice()
                .iter()
                .find(|c| c.iface_name() == Some(iface.name())),
        ) {
            if let (Some(mut base_iface), Interface::OvsInterface(oiface)) = (
                nm_conn_to_base_iface(Some(nm_dev), nm_conn, None, None),
                iface,
            ) {
                base_iface.iface_type = InterfaceType::OvsInterface;
                oiface.base = base_iface;
            }
        }
    }
}
