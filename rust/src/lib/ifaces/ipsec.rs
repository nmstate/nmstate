// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Deserializer, Serialize};

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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ikelifetime: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub salifetime: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ike: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub esp: Option<String>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u64_or_string"
    )]
    pub dpddelay: Option<u64>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u64_or_string"
    )]
    pub dpdtimeout: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dpdaction: Option<String>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "ipsec-interface",
        default,
        deserialize_with = "parse_ipsec_iface"
    )]
    pub ipsec_interface: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub authby: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rightsubnet: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub leftmodecfgclient: Option<bool>,
    #[serde(rename = "type", skip_serializing_if = "Option::is_none")]
    pub kind: Option<LibreswanConnectionType>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hostaddrfamily: Option<LibreswanAddressFamily>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub clientaddrfamily: Option<LibreswanAddressFamily>,
}

impl LibreswanConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

fn parse_ipsec_iface<'de, D>(
    deserializer: D,
) -> Result<Option<String>, D::Error>
where
    D: Deserializer<'de>,
{
    let v = serde_json::Value::deserialize(deserializer)?;

    match v {
        serde_json::Value::Number(d) => {
            if let Some(d) = d.as_u64() {
                Ok(Some(d.to_string()))
            } else {
                Err(serde::de::Error::custom(
                    "Invalid ipsec-interface value, should be \
                    unsigned integer, string 'yes' or 'no'",
                ))
            }
        }
        serde_json::Value::String(s) => match s.as_str() {
            "yes" | "no" => Ok(Some(s)),
            _ => {
                if s.parse::<u32>().is_ok() {
                    Ok(Some(s))
                } else {
                    Err(serde::de::Error::custom(
                        "Invalid ipsec-interface value, should be \
                        unsigned integer, string 'yes' or 'no'",
                    ))
                }
            }
        },
        _ => Err(serde::de::Error::custom(
            "Invalid ipsec-interface value, should be \
            unsigned integer, string 'yes' or 'no'",
        )),
    }
}

#[derive(
    Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default,
)]
#[non_exhaustive]
#[serde(rename_all = "lowercase")]
pub enum LibreswanConnectionType {
    #[default]
    Tunnel,
    Transport,
}

impl std::fmt::Display for LibreswanConnectionType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Tunnel => "tunnel",
                Self::Transport => "transport",
            }
        )
    }
}

#[derive(
    Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default,
)]
#[non_exhaustive]
#[serde(rename_all = "lowercase")]
pub enum LibreswanAddressFamily {
    #[default]
    Ipv4,
    Ipv6,
}

impl std::fmt::Display for LibreswanAddressFamily {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Ipv4 => "ipv4",
                Self::Ipv6 => "ipv6",
            }
        )
    }
}
