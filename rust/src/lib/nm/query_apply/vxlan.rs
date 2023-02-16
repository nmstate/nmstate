// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmConnection;

pub(crate) fn is_vxlan_changed(
    new_nm_conn: &NmConnection,
    cur_nm_conn: &NmConnection,
) -> bool {
    if let (Some(new_vxlan_conf), Some(cur_vxlan_conf)) =
        (new_nm_conn.vxlan.as_ref(), cur_nm_conn.vxlan.as_ref())
    {
        new_vxlan_conf.id != cur_vxlan_conf.id
    } else {
        false
    }
}
