// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmConnection;

use crate::Interface;

pub(crate) fn is_veth_peer_changed(
    new_nm_conn: &NmConnection,
    cur_nm_conn: &NmConnection,
) -> bool {
    if let (Some(new_veth_conf), Some(cur_veth_conf)) =
        (new_nm_conn.veth.as_ref(), cur_nm_conn.veth.as_ref())
    {
        new_veth_conf.peer != cur_veth_conf.peer
    } else {
        false
    }
}

pub(crate) fn is_veth_peer_in_desire(
    iface: &Interface,
    ifaces: &[&Interface],
) -> bool {
    if let Interface::Ethernet(eth_iface) = iface {
        if let Some(veth_conf) = eth_iface.veth.as_ref() {
            return ifaces.iter().any(|i| i.name() == veth_conf.peer.as_str());
        }
    }
    false
}
