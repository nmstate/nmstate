use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
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

    pub(crate) fn update_vlan(&mut self, other: &VlanInterface) {
        // TODO: this should be done by Trait
        if let Some(vlan_conf) = &mut self.vlan {
            vlan_conf.update(other.vlan.as_ref());
        } else {
            self.vlan = other.vlan.clone();
        }
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

impl VlanConfig {
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.base_iface = other.base_iface.clone();
            self.id = other.id;
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum VlanProtocol {
    #[serde(rename = "802.1q")]
    Ieee8021Q,
    #[serde(rename = "802.1ad")]
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
