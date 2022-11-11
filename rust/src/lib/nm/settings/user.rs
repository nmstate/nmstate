use std::collections::HashMap;

use crate::nm::nm_dbus::{NmConnection, NmSettingUser};

use crate::Interface;

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
