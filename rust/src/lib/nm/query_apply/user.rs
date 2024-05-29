// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use super::super::{nm_dbus::NmConnection, settings::NMSTATE_DESCRIPTION};

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

pub(crate) fn get_dispatch_variables(
    nm_conn: &NmConnection,
    iface_type_name: &str,
) -> Option<HashMap<String, String>> {
    if let Some(data) = nm_conn
        .user
        .as_ref()
        .and_then(|nm_setting| nm_setting.data.as_ref())
    {
        let mut ret: HashMap<String, String> = HashMap::new();

        for (k, v) in data {
            if let Some(name) = k.strip_prefix(&format!("{iface_type_name}.")) {
                ret.insert(name.to_string(), v.to_string());
            }
        }
        if ret.is_empty() {
            None
        } else {
            Some(ret)
        }
    } else {
        None
    }
}
