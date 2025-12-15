// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmConnection;

pub(crate) fn is_hsr_changed(
    new_nm_conn: &NmConnection,
    cur_nm_conn: &NmConnection,
) -> bool {
    if let (Some(new_hsr_conf), Some(cur_hsr_conf)) =
        (new_nm_conn.hsr.as_ref(), cur_nm_conn.hsr.as_ref())
    {
        new_hsr_conf.port1 != cur_hsr_conf.port1
            || new_hsr_conf.port2 != cur_hsr_conf.port2
            || new_hsr_conf.interlink != cur_hsr_conf.interlink
            || new_hsr_conf.multicast_spec != cur_hsr_conf.multicast_spec
            || new_hsr_conf.prp != cur_hsr_conf.prp
            || new_hsr_conf.protocol_version != cur_hsr_conf.protocol_version
    } else {
        false
    }
}
