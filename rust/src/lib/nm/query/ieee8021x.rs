// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmSetting8021X;

use crate::Ieee8021XConfig;

pub(crate) fn nm_802_1x_to_nmstate(
    nm_setting: &NmSetting8021X,
) -> Ieee8021XConfig {
    Ieee8021XConfig {
        identity: nm_setting.identity.clone(),
        private_key: nm_setting
            .private_key
            .as_deref()
            .and_then(vec_u8_to_file_path),
        eap: nm_setting.eap.clone(),
        client_cert: nm_setting
            .client_cert
            .as_deref()
            .and_then(vec_u8_to_file_path),
        ca_cert: nm_setting.ca_cert.as_deref().and_then(vec_u8_to_file_path),
        private_key_password: nm_setting.private_key_password.clone(),
    }
}

fn vec_u8_to_file_path(raw: &[u8]) -> Option<String> {
    match NmSetting8021X::glib_bytes_to_file_path(raw) {
        Ok(s) => Some(s),
        Err(e) => {
            log::error!(
                "Unsupported NetworkManager 802.1x glib bytes: {:?}, error: {}",
                raw,
                e
            );
            None
        }
    }
}
