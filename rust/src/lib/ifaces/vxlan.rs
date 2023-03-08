// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// Linux kernel VxLAN interface. The example yaml output of
/// [crate::NetworkState] with a VxLAN interface would be:
/// ```yml
/// interfaces:
/// - name: eth1.102
///   type: vxlan
///   state: up
///   mac-address: 0E:00:95:53:19:55
///   mtu: 1450
///   min-mtu: 68
///   max-mtu: 65535
///   vxlan:
///     base-iface: eth1
///     id: 102
///     remote: 239.1.1.1
///     destination-port: 1235
/// ```
pub struct VxlanInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vxlan: Option<VxlanConfig>,
}

impl Default for VxlanInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::Vxlan,
                ..Default::default()
            },
            vxlan: None,
        }
    }
}

impl VxlanInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn parent(&self) -> Option<&str> {
        self.vxlan.as_ref().and_then(|cfg| {
            if cfg.base_iface.is_empty() {
                None
            } else {
                Some(cfg.base_iface.as_str())
            }
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct VxlanConfig {
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub base_iface: String,
    #[serde(deserialize_with = "crate::deserializer::u32_or_string")]
    pub id: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub learning: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local: Option<std::net::IpAddr>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub remote: Option<std::net::IpAddr>,
    #[serde(
        rename = "destination-port",
        default,
        deserialize_with = "crate::deserializer::option_u16_or_string"
    )]
    /// Deserialize and serialize from/to `destination-port`.
    pub dst_port: Option<u16>,
}
