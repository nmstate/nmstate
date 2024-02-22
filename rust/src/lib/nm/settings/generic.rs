// SPDX-License-Identifier: Apache-2.0

use crate::nm::nm_dbus::{NmConnection, NmSettingGeneric};

use crate::UserDefinedInterface;

pub(crate) fn gen_generic_setting(
    iface: &UserDefinedInterface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_gen = NmSettingGeneric::default();
    nm_gen.device_handler = Some(iface.base.iface_type.to_string());
    nm_conn.generic = Some(nm_gen);
}
