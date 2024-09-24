// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmConnection;

pub(crate) fn is_ipvlan_changed(
    new_nm_conn: &NmConnection,
    cur_nm_conn: &NmConnection,
) -> bool {
    if let (Some(new_ipvlan_conf), Some(cur_ipvlan_conf)) =
        (new_nm_conn.ipvlan.as_ref(), cur_nm_conn.ipvlan.as_ref())
    {
        new_ipvlan_conf.parent != cur_ipvlan_conf.parent
            || new_ipvlan_conf.mode != cur_ipvlan_conf.mode
            || new_ipvlan_conf.private != cur_ipvlan_conf.private
            || new_ipvlan_conf.vepa != cur_ipvlan_conf.vepa
    } else {
        false
    }
}
