// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmConnection;

pub(crate) fn is_vlan_changed(
    new_nm_conn: &NmConnection,
    cur_nm_conn: &NmConnection,
) -> bool {
    if let (Some(new_vlan_conf), Some(cur_vlan_conf)) =
        (new_nm_conn.vlan.as_ref(), cur_nm_conn.vlan.as_ref())
    {
        new_vlan_conf.id != cur_vlan_conf.id
            || new_vlan_conf.protocol != cur_vlan_conf.protocol
    } else {
        false
    }
}
