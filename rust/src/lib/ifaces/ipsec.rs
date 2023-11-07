// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType, NetworkState};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// The libreswan Ipsec interface. This interface does not exist in kernel
/// space but only exist in user space tools.
/// This is the example yaml output of [crate::NetworkState] with a libreswan
/// ipsec connection:
/// ```yaml
/// ---
/// interfaces:
/// - name: hosta_conn
///   type: ipsec
///   ipv4:
///     enabled: true
///     dhcp: true
///   libreswan:
///     right: 192.0.2.252
///     rightid: '@hostb.example.org'
///     left: 192.0.2.251
///     leftid: '%fromcert'
///     leftcert: hosta.example.org
///     ikev2: insist
/// ```
pub struct IpsecInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub libreswan: Option<LibreswanConfig>,
}

impl Default for IpsecInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::Ipsec,
                ..Default::default()
            },
            libreswan: None,
        }
    }
}

impl IpsecInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn hide_secrets(&mut self) {
        if let Some(c) = self.libreswan.as_mut() {
            if c.psk.is_some() {
                c.psk = Some(NetworkState::PASSWORD_HID_BY_NMSTATE.to_string());
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(deny_unknown_fields)]
#[non_exhaustive]
pub struct LibreswanConfig {
    pub right: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rightid: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rightrsasigkey: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub left: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub leftid: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub leftrsasigkey: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub leftcert: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ikev2: Option<String>,
    /// PSK authentication, if not defined, will use X.509 PKI authentication
    #[serde(skip_serializing_if = "Option::is_none")]
    pub psk: Option<String>,
}

impl LibreswanConfig {
    pub fn new() -> Self {
        Self::default()
    }
}
