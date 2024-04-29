// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::nm::nm_dbus::{NmConnection, NmSettingUser};

use crate::{DispatchInterface, Interface, InterfaceType};

pub(crate) const NMSTATE_DESCRIPTION: &str = "nmstate.interface.description";

pub(crate) fn gen_nm_user_setting(
    iface: &Interface,
    nm_conn: &mut NmConnection,
) {
    if let Some(description) = iface.base_iface().description.as_ref() {
        let mut data: HashMap<String, String> = HashMap::new();
        if !description.is_empty() {
            data.insert(
                NMSTATE_DESCRIPTION.to_string(),
                description.to_string(),
            );
        }
        let mut nm_setting = NmSettingUser::default();
        nm_setting.data = Some(data);
        nm_conn.user = Some(nm_setting);
    }
}

pub(crate) fn gen_dispatch_iface_setting(
    iface: &DispatchInterface,
    nm_conn: &mut NmConnection,
) {
    if let Some(variables) = iface
        .base
        .dispatch
        .as_ref()
        .and_then(|d| d.variables.as_ref())
    {
        let mut nm_user = nm_conn.user.as_ref().cloned().unwrap_or_default();
        let data = nm_user.data.get_or_insert(HashMap::new());
        let iface_type_str = if iface.base.iface_type == InterfaceType::Dispatch
        {
            if let Some(dispatch_type) =
                iface.base.dispatch.as_ref().and_then(|d| d.kind.as_deref())
            {
                dispatch_type.to_string()
            } else {
                log::error!(
                    "BUG: The for_apply dispatch interface should \
                    always has type defined, but not None for {iface:?}"
                );
                return;
            }
        } else {
            log::warn!(
                "Dispatch variable for non-dispatch interface is not \
                supported yet, ignoring"
            );
            return;
        };
        for (k, v) in variables.iter() {
            data.insert(format!("{}.{}", iface_type_str, k), v.to_string());
        }
        nm_conn.user = Some(nm_user);
    }
}
