// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmConnection;

use super::super::settings::NMSTATE_DESCRIPTION;

pub(crate) fn get_description(nm_conn: &NmConnection) -> Option<String> {
    Some(
        nm_conn
            .user
            .as_ref()
            .and_then(|nm_setting| nm_setting.data.as_ref())
            .and_then(|data| data.get(NMSTATE_DESCRIPTION))
            .map(|s| s.to_string())
            .unwrap_or_default(),
    )
}
