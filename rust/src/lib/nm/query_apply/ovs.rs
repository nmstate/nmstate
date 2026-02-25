// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use super::{
    super::{
        NmConnectionMatcher,
        connection::is_uuid,
        nm_dbus::{NmApi, NmConnection, NmIfaceType},
        show::fill_iface_by_nm_conn_data,
    },
    connection::delete_connections,
};
use crate::{
    InterfaceType, MergedInterface, MergedInterfaces, NetworkState,
    NmstateError,
};

// When OVS system interface got detached from OVS bridge, we should remove its
// ovs port also.
pub(crate) async fn delete_orphan_ovs_ports(
    nm_api: &mut NmApi<'_>,
    merged_ifaces: &MergedInterfaces,
    conn_matcher: &NmConnectionMatcher,
    nm_conns_to_activate: &[NmConnection],
) -> Result<(), NmstateError> {
    let mut orphan_ovs_port_uuids: Vec<&str> = Vec::new();
    let uuid_to_activate: HashSet<&str> = nm_conns_to_activate
        .iter()
        .filter_map(|c| c.uuid())
        .collect();
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
            let ovs_iface_nm_conns = conn_matcher.get_saved_by_name_type(
                iface.merged.name(),
                &NmIfaceType::from(&iface.merged.iface_type()),
            );

            for ovs_port_name in ovs_iface_nm_conns
                .filter_map(|ovs_iface_nm_conn| ovs_iface_nm_conn.controller())
            {
                if is_uuid(ovs_port_name) {
                    // The OVS bond might still have ports even
                    // specified interface detached, this OVS bond will
                    // be included in `nm_conns_to_activate()`, we just
                    // do not remove connection pending for activation.
                    if !uuid_to_activate.contains(ovs_port_name) {
                        log::info!(
                            "Deleting orphan OVS port connection {} as \
                             interface {}({}) detached from OVS bridge",
                            ovs_port_name,
                            iface.merged.name(),
                            iface.merged.iface_type()
                        );
                        orphan_ovs_port_uuids.push(ovs_port_name);
                    }
                } else {
                    for ovs_port_nm_conn in conn_matcher.get_saved_by_name_type(
                        ovs_port_name,
                        &NmIfaceType::OvsPort,
                    ) {
                        if let Some(uuid) = ovs_port_nm_conn.uuid() {
                            // The OVS bond might still have ports even
                            // specified interface detached, this OVS bond will
                            // be included in `nm_conns_to_activate()`, we just
                            // do not remove connection pending for activation.
                            if !uuid_to_activate.contains(uuid) {
                                log::info!(
                                    "Deleting orphan OVS port connection {} \
                                     as interface {}({}) detached from OVS \
                                     bridge",
                                    uuid,
                                    iface.merged.name(),
                                    iface.merged.iface_type()
                                );
                                orphan_ovs_port_uuids.push(uuid);
                            }
                        }
                    }
                }
            }
        }
    }
    delete_connections(nm_api, orphan_ovs_port_uuids.as_slice()).await
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
    conn_matcher: &NmConnectionMatcher,
) {
    for iface in net_state
        .interfaces
        .kernel_ifaces
        .values_mut()
        .filter(|i| i.iface_type() == InterfaceType::OvsInterface)
    {
        if let Some(nm_conn) = conn_matcher
            .get_applied_by_name_type(iface.name(), &NmIfaceType::Tun)
        {
            fill_iface_by_nm_conn_data(iface, Some(nm_conn), None, None);
        }
    }
}
