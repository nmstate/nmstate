// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{NmConnection, NmSetting8021X};

use crate::{Interface, NetworkState};

pub(crate) fn gen_nm_802_1x_setting(
    iface: &Interface,
    nm_conn: &mut NmConnection,
) {
    if let Some(conf) = iface.base_iface().ieee8021x.as_ref() {
        let mut nm_setting = NmSetting8021X::default();
        nm_setting.identity.clone_from(&conf.identity);
        nm_setting.eap.clone_from(&conf.eap);
        nm_setting.private_key = conf
            .private_key
            .as_deref()
            .map(NmSetting8021X::file_path_to_glib_bytes);
        nm_setting.client_cert = conf
            .client_cert
            .as_deref()
            .map(NmSetting8021X::file_path_to_glib_bytes);
        nm_setting.ca_cert = conf
            .ca_cert
            .as_deref()
            .map(NmSetting8021X::file_path_to_glib_bytes);
        if conf.private_key_password.as_deref()
            == Some(NetworkState::PASSWORD_HID_BY_NMSTATE)
        {
            if let Some(cur_pass) = nm_conn
                .ieee8021x
                .as_ref()
                .and_then(|c| c.private_key_password.as_deref())
            {
                nm_setting.private_key_password = Some(cur_pass.to_string());
            }
        } else {
            nm_setting
                .private_key_password
                .clone_from(&conf.private_key_password);
        }
        nm_setting.phase2_auth.clone_from(&conf.phase2_auth);
        if conf.password.as_deref()
            == Some(NetworkState::PASSWORD_HID_BY_NMSTATE)
        {
            if let Some(cur_pass) = nm_conn
                .ieee8021x
                .as_ref()
                .and_then(|c| c.password.as_deref())
            {
                nm_setting.password = Some(cur_pass.to_string());
            }
        } else {
            nm_setting.password.clone_from(&conf.password);
        }
        nm_conn.ieee8021x = Some(nm_setting);
    }
}
