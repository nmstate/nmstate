use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// Linux kernel VLAN interface. The example yaml output of
/// [crate::NetworkState] with a VLAN interface would be:
/// ```yaml
/// interfaces:
/// - name: eth1.101
///   type: vlan
///   state: up
///   mac-address: BE:E8:17:8F:D2:70
///   mtu: 1500
///   max-mtu: 65535
///   wait-ip: any
///   ipv4:
///     enabled: false
///   ipv6:
///     enabled: false
///   accept-all-mac-addresses: false
///   vlan:
///     base-iface: eth1
///     id: 101
/// ```
pub struct VlanInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vlan: Option<VlanConfig>,
}

impl Default for VlanInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::Vlan,
                ..Default::default()
            },
            vlan: None,
        }
    }
}

impl VlanInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn parent(&self) -> Option<&str> {
        self.vlan.as_ref().map(|cfg| cfg.base_iface.as_str())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct VlanConfig {
    pub base_iface: String,
    #[serde(deserialize_with = "crate::deserializer::u16_or_string")]
    pub id: u16,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum VlanProtocol {
    #[serde(rename = "802.1q")]
    /// Deserialize and serialize from/to `802.1q`.
    Ieee8021Q,
    #[serde(rename = "802.1ad")]
    /// Deserialize and serialize from/to `802.1ad`.
    Ieee8021Ad,
}

impl Default for VlanProtocol {
    fn default() -> Self {
        Self::Ieee8021Q
    }
}

impl std::fmt::Display for VlanProtocol {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Ieee8021Q => "802.1q",
                Self::Ieee8021Ad => "802.1ad",
            }
        )
    }
}
