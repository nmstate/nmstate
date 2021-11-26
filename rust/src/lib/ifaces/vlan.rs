use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
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
        Default::default()
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

    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.base.pre_verify_cleanup();
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub struct VlanConfig {
    pub base_iface: String,
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
