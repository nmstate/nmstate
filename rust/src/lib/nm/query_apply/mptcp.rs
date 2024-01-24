// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmConnection;

pub(crate) fn is_mptcp_flags_changed(
    nm_conn: &NmConnection,
    activated_nm_con: &NmConnection,
) -> bool {
    match (
        nm_conn.connection.as_ref().and_then(|c| c.mptcp_flags),
        activated_nm_con
            .connection
            .as_ref()
            .and_then(|c| c.mptcp_flags),
    ) {
        (Some(flags), Some(cur_flags)) => flags == cur_flags,
        _ => false,
    }
}
