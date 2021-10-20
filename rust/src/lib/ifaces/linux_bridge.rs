use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LinuxBridgeInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bridge: Option<LinuxBridgeConfig>,
}

impl Default for LinuxBridgeInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::LinuxBridge;
        Self { base, bridge: None }
    }
}

impl LinuxBridgeInterface {
    pub(crate) fn update_bridge(&mut self, other: &LinuxBridgeInterface) {
        if let Some(br_conf) = &mut self.bridge {
            br_conf.update(other.bridge.as_ref());
        } else {
            self.bridge = other.bridge.clone();
        }
    }

    pub(crate) fn ports(&self) -> Option<Vec<&str>> {
        let mut port_names = Vec::new();
        if let Some(br_conf) = &self.bridge {
            if let Some(ports) = &br_conf.port {
                for port in ports {
                    port_names.push(port.name.as_str());
                }
            }
        }
        Some(port_names)
    }

    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.base.pre_verify_cleanup();
    }

    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub struct LinuxBridgeConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<LinuxBridgeOptions>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub port: Option<Vec<LinuxBridgePortConfig>>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub struct LinuxBridgePortConfig {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stp_hairpin_mode: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stp_path_cost: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stp_priority: Option<u16>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub struct LinuxBridgeOptions {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stp: Option<LinuxBridgeStpOptions>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub struct LinuxBridgeStpOptions {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enabled: Option<bool>,
}

impl LinuxBridgeConfig {
    pub(crate) fn update(&mut self, other: Option<&LinuxBridgeConfig>) {
        if let Some(other) = other {
            self.options = other.options.clone();
            self.port = other.port.clone();
        }
    }
}
