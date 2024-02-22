use std::collections::HashMap;

use crate::nm::nm_dbus::{NmConnection, NmSettingUser};

use crate::{Interface, UserDefinedInterface};

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

pub(crate) fn gen_user_defined_iface_setting(
    iface: &UserDefinedInterface,
    nm_conn: &mut NmConnection,
) {
    if let Some(conf) = iface.user_defined.as_ref() {
        let mut nm_user = nm_conn.user.as_ref().cloned().unwrap_or_default();
        let data = nm_user.data.get_or_insert(HashMap::new());
        for (k, v) in conf.iter() {
            data.insert(
                format!("{}.{}", iface.base.iface_type, k),
                v.to_string(),
            );
        }
        nm_conn.user = Some(nm_user);
    }
}
