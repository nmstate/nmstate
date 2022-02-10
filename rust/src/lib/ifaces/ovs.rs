use std::convert::TryFrom;

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, ErrorKind, InterfaceType, NmstateError};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct OvsBridgeInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bridge: Option<OvsBridgeConfig>,
}

impl Default for OvsBridgeInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::OvsBridge;
        Self { base, bridge: None }
    }
}

impl OvsBridgeInterface {
    pub(crate) fn update_ovs_bridge(&mut self, other: &OvsBridgeInterface) {
        if let Some(br_conf) = &mut self.bridge {
            br_conf.update(other.bridge.as_ref());
        } else {
            self.bridge = other.bridge.clone();
        }
    }

    pub(crate) fn ports(&self) -> Option<Vec<&str>> {
        let mut port_names = Vec::new();
        if let Some(br_conf) = &self.bridge {
            if let Some(port_confs) = &br_conf.ports {
                for port_conf in port_confs {
                    if let Some(bond_conf) = &port_conf.bond {
                        for port_name in bond_conf.ports() {
                            port_names.push(port_name);
                        }
                    } else {
                        port_names.push(port_conf.name.as_str());
                    }
                }
            }
        }
        Some(port_names)
    }

    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.sort_ports()
    }

    pub fn new() -> Self {
        Self::default()
    }

    fn sort_ports(&mut self) {
        if let Some(ref mut br_conf) = self.bridge {
            if let Some(ref mut port_confs) = &mut br_conf.ports {
                port_confs.sort_unstable_by_key(|p| p.name.clone());
                for port_conf in port_confs {
                    if let Some(ref mut bond_conf) = port_conf.bond {
                        bond_conf.sort_ports();
                    }
                }
            }
        }
    }

    pub(crate) fn port_confs(&self) -> Vec<&OvsBridgePortConfig> {
        let mut ret: Vec<&OvsBridgePortConfig> = Vec::new();
        if let Some(br_conf) = &self.bridge {
            if let Some(port_confs) = &br_conf.ports {
                for port_conf in port_confs {
                    ret.push(port_conf)
                }
            }
        }
        ret
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct OvsBridgeConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<OvsBridgeOptions>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "port")]
    pub ports: Option<Vec<OvsBridgePortConfig>>,
}

impl OvsBridgeConfig {
    pub(crate) fn update(&mut self, other: Option<&OvsBridgeConfig>) {
        if let Some(other) = other {
            self.ports = other.ports.clone();
        }
    }

    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct OvsBridgeOptions {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stp: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rstp: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mcast_snooping_enable: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fail_mode: Option<String>,
}

impl OvsBridgeOptions {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct OvsBridgePortConfig {
    pub name: String,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "link-aggregation"
    )]
    pub bond: Option<OvsBridgeBondConfig>,
}

impl OvsBridgePortConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct OvsInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
}

impl Default for OvsInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::OvsInterface;
        Self { base }
    }
}

impl OvsInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn parent(&self) -> Option<&str> {
        self.base.controller.as_deref()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct OvsBridgeBondConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mode: Option<OvsBridgeBondMode>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "port")]
    pub ports: Option<Vec<OvsBridgeBondPortConfig>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bond_downdelay: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bond_updelay: Option<u32>,
}

impl OvsBridgeBondConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn ports(&self) -> Vec<&str> {
        let mut port_names: Vec<&str> = Vec::new();
        if let Some(ports) = &self.ports {
            for port in ports {
                port_names.push(&port.name);
            }
        }
        port_names
    }
    pub(crate) fn sort_ports(&mut self) {
        if let Some(ref mut bond_ports) = self.ports {
            bond_ports.sort_unstable_by_key(|p| p.name.clone())
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct OvsBridgeBondPortConfig {
    pub name: String,
}

impl OvsBridgeBondPortConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum OvsBridgeBondMode {
    ActiveBackup,
    BalanceSlb,
    BalanceTcp,
    Lacp,
}

impl Default for OvsBridgeBondMode {
    fn default() -> Self {
        Self::BalanceSlb
    }
}

impl TryFrom<&str> for OvsBridgeBondMode {
    type Error = NmstateError;
    fn try_from(value: &str) -> Result<Self, Self::Error> {
        match value {
            "active-backup" => Ok(Self::ActiveBackup),
            "balance-slb" => Ok(Self::BalanceSlb),
            "balance-tcp" => Ok(Self::BalanceTcp),
            "lacp" => Ok(Self::Lacp),
            _ => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!("Unsupported OVS Bond mode {}", value),
            )),
        }
    }
}

impl std::fmt::Display for OvsBridgeBondMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::ActiveBackup => "active-backup",
                Self::BalanceSlb => "balance-slb",
                Self::BalanceTcp => "balance-tcp",
                Self::Lacp => "lacp",
            }
        )
    }
}
