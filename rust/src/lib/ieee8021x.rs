// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::NetworkState;

#[derive(Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
/// The IEEE 802.1X authentication configuration. The example yaml output of
/// [crate::NetworkState] with IEEE 802.1X authentication interface:
/// ```yml
/// ---
/// interfaces:
///   - name: eth1
///     type: ethernet
///     state: up
///     802.1x:
///       ca-cert: /etc/pki/802-1x-test/ca.crt
///       client-cert: /etc/pki/802-1x-test/client.example.org.crt
///       eap-methods:
///         - tls
///       identity: client.example.org
///       private-key: /etc/pki/802-1x-test/client.example.org.key
///       private-key-password: password
/// ```
pub struct Ieee8021XConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub identity: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "eap-methods")]
    /// Deserialize and serialize from/to `eap-methods`.
    pub eap: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Deserialize and serialize from/to `private-key`.
    pub private_key: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Deserialize and serialize from/to `client-cert`.
    pub client_cert: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Deserialize and serialize from/to `ca-cert`.
    pub ca_cert: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Deserialize and serialize from/to `private-key-password`.
    /// Replaced to `<_password_hid_by_nmstate>` when querying.
    pub private_key_password: Option<String>,
}

impl Ieee8021XConfig {
    pub(crate) fn hide_secrets(&mut self) {
        if self.private_key_password.is_some() {
            self.private_key_password =
                Some(NetworkState::PASSWORD_HID_BY_NMSTATE.to_string());
        }
    }
}

impl std::fmt::Debug for Ieee8021XConfig {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Ieee8021XConfig")
            .field("identity", &self.identity)
            .field("eap", &self.eap)
            .field("private_key", &self.private_key)
            .field("client_cert", &self.client_cert)
            .field("ca_cert", &self.ca_cert)
            .field(
                "private_key_password",
                &Some(NetworkState::PASSWORD_HID_BY_NMSTATE.to_string()),
            )
            .finish()
    }
}
