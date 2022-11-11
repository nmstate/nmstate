// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{NmApi, NmConnection};

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

pub(crate) fn is_mptcp_supported(nm_api: &NmApi) -> bool {
    let version_str = nm_api.version().unwrap_or_default();
    let versions: Vec<&str> = version_str.split('.').collect();
    if versions.len() < 2 {
        return false;
    }
    if let (Ok(major), Ok(minor)) =
        (versions[0].parse::<i32>(), versions[1].parse::<i32>())
    {
        major >= 1 && minor >= 40
    } else {
        false
    }
}

pub(crate) fn remove_nm_mptcp_set(nm_conn: &mut NmConnection) {
    if let Some(nm_conn_set) = nm_conn.connection.as_mut() {
        nm_conn_set.mptcp_flags = None;
    }
}
