// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{NmApi, NmConnection, NmDevice, NmIfaceType};
use super::super::{
    profile::NmProfile,
    query_apply::profile::{delete_profiles, is_uuid},
    settings::{gen_nmstate_iface_for_ovs_port, get_exist_profile},
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
    nm_profiles: &[NmProfile],
) -> Result<(), NmstateError> {
    let uuids_to_activate: Vec<&str> =
        nm_profiles.iter().filter_map(|p| p.conn.uuid()).collect();
    let mut orphan_ovs_port_uuids: Vec<&str> = Vec::new();

    for iface in merged_ifaces.kernel_ifaces.values().filter_map(|i| {
        if i.is_changed() && iface_was_ovs_sys_iface(i) {
            i.current.as_ref()
        } else {
            None
        }
    }) {
        if let Some(ovs_port_conn) =
            get_ovs_port_profile_for_ovs_sys_iface(exist_nm_conns, iface)
        {
            if let Some(uuid) = ovs_port_conn.uuid() {
                if !uuids_to_activate.contains(&uuid) {
                    log::info!(
                        "Deleting orphan OVS port connection {} \
                         as interface {}({}) is detaching from OVS bridge",
                        uuid,
                        iface.name(),
                        iface.iface_type()
                    );
                    orphan_ovs_port_uuids.push(uuid);
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
        && iface
            .for_apply
            .as_ref()
            .and_then(|i| i.base_iface().controller_type.as_ref())
            != Some(&InterfaceType::OvsBridge)
}

pub(crate) fn merge_ovs_netdev_tun_iface(
    net_state: &mut NetworkState,
    nm_devs: &[NmDevice],
    nm_conns: &[NmConnection],
) {
    let tun_nm_devs: Vec<&NmDevice> = nm_devs
        .iter()
        .filter(|d| d.iface_type == NmIfaceType::Tun)
        .collect();
    let tun_nm_conns: Vec<&NmConnection> = nm_conns
        .iter()
        .filter(|c| c.iface_type() == Some(&NmIfaceType::Tun))
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

fn get_ovs_port_profile_for_ovs_sys_iface<'a>(
    exist_nm_conns: &'a [NmConnection],
    iface: &Interface,
) -> Option<&'a NmConnection> {
    if let Some(ovs_iface_conn) = get_exist_profile(exist_nm_conns, iface, &[])
    {
        if ovs_iface_conn
            .connection
            .as_ref()
            .and_then(|c| c.controller_type.as_ref())
            == Some(&NmIfaceType::OvsPort)
        {
            let ovs_port_name = ovs_iface_conn
                .connection
                .as_ref()
                .and_then(|c| c.controller.as_ref())?;

            if is_uuid(ovs_port_name) {
                return exist_nm_conns
                    .iter()
                    .find(|nm_conn| nm_conn.uuid() == Some(ovs_port_name));
            } else {
                return get_exist_profile(
                    exist_nm_conns,
                    &gen_nmstate_iface_for_ovs_port(ovs_port_name, None),
                    &[],
                );
            }
        }
    }
    None
}
