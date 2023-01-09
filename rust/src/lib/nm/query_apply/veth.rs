// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmConnection;

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
