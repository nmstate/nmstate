// SPDX-License-Identifier: Apache-2.0

use crate::nm::nm_dbus::{NmConnection, NmSettingGeneric};

use crate::DispatchInterface;

pub(crate) fn gen_generic_setting(
    iface: &DispatchInterface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_gen = NmSettingGeneric::default();
    if let Some(dispatch_type) =
        &iface.base.dispatch.as_ref().and_then(|d| d.kind.as_deref())
    {
        nm_gen.device_handler = Some(dispatch_type.to_string());
    }
    nm_conn.generic = Some(nm_gen);
}

pub(crate) fn get_dispath_type(nm_conn: &NmConnection) -> Option<String> {
    nm_conn.generic.as_ref().and_then(|g| {
        if let Some(h) = g.device_handler.as_ref() {
            if h.is_empty() {
                None
            } else {
                Some(h.to_string())
            }
        } else {
            None
        }
    })
}
