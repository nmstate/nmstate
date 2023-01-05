// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmConnection;

pub(crate) fn is_vrf_table_id_changed(
    new_nm_conn: &NmConnection,
    cur_nm_conn: &NmConnection,
) -> bool {
    if let (Some(new_vrf_conf), Some(cur_vrf_conf)) =
        (new_nm_conn.vrf.as_ref(), cur_nm_conn.vrf.as_ref())
    {
        new_vrf_conf.table != cur_vrf_conf.table
    } else {
        false
    }
}
