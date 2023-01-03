// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, BridgePortVlanConfig, ErrorKind, InterfaceType, NmstateError,
};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// OpenvSwitch bridge interface. Example yaml output of [crate::NetworkState]
/// with an OVS bridge:
/// ```yaml
/// ---
/// interfaces:
/// - name: br0
///   type: ovs-interface
///   state: up
///   ipv4:
///     address:
///     - ip: 192.0.2.252
///       prefix-length: 24
///     - ip: 192.0.2.251
///       prefix-length: 24
///     dhcp: false
///     enabled: true
///   ipv6:
///     address:
///       - ip: 2001:db8:2::1
///         prefix-length: 64
///       - ip: 2001:db8:1::1
///         prefix-length: 64
///     autoconf: false
///     dhcp: false
///     enabled: true
/// - name: br0
///   type: ovs-bridge
///   state: up
///   bridge:
///     port:
///     - name: br0
///     - name: eth1
/// ```
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
    // Return None when desire state does not mention ports
    pub(crate) fn ports(&self) -> Option<Vec<&str>> {
        if let Some(br_conf) = &self.bridge {
            if let Some(port_confs) = &br_conf.ports {
                let mut port_names = Vec::new();
                for port_conf in port_confs {
                    if let Some(bond_conf) = &port_conf.bond {
                        for port_name in bond_conf.ports() {
                            port_names.push(port_name);
                        }
                    } else {
                        port_names.push(port_conf.name.as_str());
                    }
                }
                return Some(port_names);
            }
        }
        None
    }

    pub fn new() -> Self {
        Self::default()
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

    pub(crate) fn create_ovs_iface_is_empty_ports(
        &mut self,
        current: Option<&Self>,
    ) -> Option<OvsInterface> {
        if (current.is_none()
            && self.ports().map(|p| p.is_empty()).unwrap_or(true))
            || (current.is_some()
                && self.ports().map(|p| p.is_empty()) == Some(true))
        {
            log::warn!(
                "OVS bridge {} cannot exist with empty port list, adding a \
                OVS internal interface with the same name",
                self.base.name.as_str()
            );
            if let Some(br_conf) = self.bridge.as_mut() {
                br_conf.ports = Some(vec![OvsBridgePortConfig {
                    name: self.base.name.clone(),
                    ..Default::default()
                }])
            } else {
                self.bridge = Some(OvsBridgeConfig {
                    ports: Some(vec![OvsBridgePortConfig {
                        name: self.base.name.clone(),
                        ..Default::default()
                    }]),
                    ..Default::default()
                })
            }
            Some(OvsInterface::new_with_name_and_ctrl(
                self.base.name.as_str(),
                self.base.name.as_str(),
            ))
        } else {
            None
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct OvsBridgeConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<OvsBridgeOptions>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "port",
        alias = "ports"
    )]
    /// Serialize to 'port'. Deserialize from `port` or `ports`.
    pub ports: Option<Vec<OvsBridgePortConfig>>,
}

impl OvsBridgeConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct OvsBridgeOptions {
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub stp: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub rstp: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    /// Deserialize and serialize from/to `mcast-snooping-enable`.
    pub mcast_snooping_enable: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Deserialize and serialize from/to `fail-mode`.
    pub fail_mode: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Set to `netdev` for DPDK.
    /// Deserialize and serialize from/to `datapath`.
    pub datapath: Option<String>,
}

impl OvsBridgeOptions {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct OvsBridgePortConfig {
    pub name: String,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "link-aggregation"
    )]
    pub bond: Option<OvsBridgeBondConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vlan: Option<BridgePortVlanConfig>,
}

impl OvsBridgePortConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// OpenvSwitch internal interface. Example yaml output of [crate::NetworkState]
/// with an DPDK enabled OVS interface:
/// ```yml
/// ---
/// interfaces:
/// - name: ovs0
///   type: ovs-interface
///   state: up
///   dpdk:
///     devargs: "0000:af:00.1"
///     rx-queue: 100
/// - name: br0
///   type: ovs-bridge
///   state: up
///   bridge:
///     options:
///       datapath: "netdev"
///     port:
///     - name: ovs0
/// ovs-db:
///   other_config:
///     dpdk-init: "true"
/// ```
///
/// The yaml example of OVS pathing:
/// ```yml
/// ---
/// interfaces:
/// - name: patch0
///   type: ovs-interface
///   state: up
///   patch:
///     peer: patch1
/// - name: ovs-br0
///   type: ovs-bridge
///   state: up
///   bridge:
///     port:
///     - name: patch0
/// - name: patch1
///   type: ovs-interface
///   state: up
///   patch:
///     peer: patch0
/// - name: ovs-br1
///   type: ovs-bridge
///   state: up
///   bridge:
///     port:
///     - name: patch1
/// ```
pub struct OvsInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub patch: Option<OvsPatchConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dpdk: Option<OvsDpdkConfig>,
}

impl Default for OvsInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::OvsInterface;
        Self {
            base,
            patch: None,
            dpdk: None,
        }
    }
}

impl OvsInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn new_with_name_and_ctrl(
        iface_name: &str,
        ctrl_name: &str,
    ) -> Self {
        let mut base_iface = BaseInterface::new();
        base_iface.name = iface_name.to_string();
        base_iface.iface_type = InterfaceType::OvsInterface;
        base_iface.controller = Some(ctrl_name.to_string());
        base_iface.controller_type = Some(InterfaceType::OvsBridge);
        let mut iface = Self::new();
        iface.base = base_iface;
        iface
    }

    pub(crate) fn parent(&self) -> Option<&str> {
        self.base.controller.as_deref()
    }

    // OVS patch interface cannot have MTU or IP configuration
    pub(crate) fn pre_edit_cleanup(&self) -> Result<(), NmstateError> {
        if self.patch.is_some() {
            if self.base.mtu.is_some() {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "OVS patch interface is not allowed to hold MTU \
                        configuration, interface name {}",
                        self.base.name.as_str()
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            }
            if self.base.ipv4.as_ref().map(|c| c.enabled) == Some(true)
                || self.base.ipv6.as_ref().map(|c| c.enabled) == Some(true)
            {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "OVS patch interface is not allowed to hold IP \
                        configuration, interface name {}",
                        self.base.name.as_str()
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[non_exhaustive]
/// The example yaml output of OVS bond:
/// ```yml
/// ---
/// interfaces:
/// - name: eth1
///   type: ethernet
///   state: up
/// - name: eth2
///   type: ethernet
///   state: up
/// - name: br0
///   type: ovs-bridge
///   state: up
///   bridge:
///     port:
///     - name: veth1
///     - name: ovs0
///     - name: bond1
///       link-aggregation:
///         mode: balance-slb
///         port:
///           - name: eth2
///           - name: eth1
/// ```
pub struct OvsBridgeBondConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mode: Option<OvsBridgeBondMode>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "port",
        alias = "ports"
    )]
    /// Serialize to 'port'. Deserialize from `port` or `ports`.
    pub ports: Option<Vec<OvsBridgeBondPortConfig>>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string",
        rename = "bond-downdelay"
    )]
    /// Deserialize and serialize from/to `bond-downdelay`.
    pub bond_downdelay: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string",
        rename = "bond-updelay"
    )]
    /// Deserialize and serialize from/to `bond-updelay`.
    pub bond_updelay: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// OpenvSwitch specific `other_config` for OVS bond. Please refer to
    /// manpage `ovs-vswitchd.conf.db(5)` for more detail.
    /// Set to None for remove specific entry.
    pub other_config: Option<HashMap<String, Option<String>>>,
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
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
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

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum OvsBridgeBondMode {
    /// Deserialize and serialize from/to `active-backup`.
    ActiveBackup,
    /// Deserialize and serialize from/to `balance-slb`.
    BalanceSlb,
    /// Deserialize and serialize from/to `balance-tcp`.
    BalanceTcp,
    /// Deserialize and serialize from/to `lacp`.
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
                format!("Unsupported OVS Bond mode {value}"),
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

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(deny_unknown_fields)]
#[non_exhaustive]
pub struct OvsPatchConfig {
    pub peer: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
#[non_exhaustive]
pub struct OvsDpdkConfig {
    pub devargs: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Deserialize and serialize from/to `rx-queue`.
    pub rx_queue: Option<u32>,
}
