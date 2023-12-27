// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;
use std::convert::TryFrom;

use serde::{de, Deserialize, Deserializer, Serialize};

use crate::{
    BaseInterface, BridgePortVlanConfig, ErrorKind, Interface, InterfaceState,
    InterfaceType, LinuxBridgeStpOptions, MergedInterface, MergedInterfaces,
    NmstateError, OvsDbIfaceConfig,
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
    pub(crate) fn post_deserialize_cleanup(&mut self) {
        if let Some(i) = self.bridge.as_mut() {
            i.post_deserialize_cleanup()
        }
    }

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

    pub(crate) fn sort_ports(&mut self) {
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

    // * OVS Bridge cannot have MTU, IP
    pub(crate) fn sanitize(
        &mut self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if let Some(mtu) = self.base.mtu.as_ref() {
            if is_desired {
                log::warn!(
                    "OVS Bridge {} could not hold 'mtu:{mtu}' configuration \
                    as it only exists in OVS database, ignoring",
                    self.base.name.as_str()
                );
            }
        }
        self.base.mtu = None;
        self.base.ipv4 = None;
        self.base.ipv6 = None;
        self.sort_ports();

        if let Some(br_conf) = self.bridge.as_mut() {
            br_conf.sanitize(is_desired)?;
        }

        Ok(())
    }

    // Only support remove non-bonding port or the bond itself as bond require
    // two ports, removal any of them will trigger error.
    pub(crate) fn remove_port(&mut self, port_name: &str) {
        if let Some(br_ports) = self
            .bridge
            .as_mut()
            .and_then(|br_conf| br_conf.ports.as_mut())
        {
            br_ports.retain(|p| p.name.as_str() != port_name)
        }
    }

    pub(crate) fn change_port_name(
        &mut self,
        origin_name: &str,
        new_name: String,
    ) {
        if let Some(index) = self
            .bridge
            .as_ref()
            .and_then(|br_conf| br_conf.ports.as_ref())
            .and_then(|ports| {
                ports.iter().position(|port| port.name == origin_name)
            })
        {
            if let Some(ports) = self
                .bridge
                .as_mut()
                .and_then(|br_conf| br_conf.ports.as_mut())
            {
                ports[index].name = new_name;
            }
        } else if let Some(index) = self
            .bridge
            .as_ref()
            .and_then(|br_conf| br_conf.ports.as_ref())
            .and_then(|ports| {
                ports.iter().position(|port_conf| {
                    port_conf
                        .bond
                        .as_ref()
                        .and_then(|bond_conf| bond_conf.ports.as_ref())
                        .map(|bond_port_confs| {
                            bond_port_confs
                                .iter()
                                .any(|bond_conf| bond_conf.name == origin_name)
                        })
                        .unwrap_or_default()
                })
            })
        {
            if let Some(bond_port_confs) = self
                .bridge
                .as_mut()
                .and_then(|br_conf| br_conf.ports.as_mut())
                .and_then(|ports| ports.get_mut(index))
                .and_then(|port_conf| port_conf.bond.as_mut())
                .and_then(|bond_conf| bond_conf.ports.as_mut())
            {
                for bond_port_conf in bond_port_confs {
                    if bond_port_conf.name == origin_name {
                        bond_port_conf.name = new_name;
                        break;
                    }
                }
            }
        }
    }

    // * Merge port vlan config if not desired
    pub(crate) fn special_merge(&mut self, desired: &Self, current: &Self) {
        let mut new_ports = Vec::new();
        if let (Some(des_ports), Some(cur_ports)) = (
            desired.bridge.as_ref().and_then(|b| b.ports.as_ref()),
            current.bridge.as_ref().and_then(|b| b.ports.as_ref()),
        ) {
            for des_port_conf in des_ports {
                let mut new_port = des_port_conf.clone();
                if des_port_conf.vlan.is_none() {
                    for cur_port_conf in cur_ports {
                        if cur_port_conf.name.as_str()
                            == des_port_conf.name.as_str()
                        {
                            new_port.vlan = cur_port_conf.vlan.clone();
                            break;
                        }
                    }
                }
                new_ports.push(new_port);
            }
        }
        if !new_ports.is_empty() {
            if let Some(br_conf) = self.bridge.as_mut() {
                br_conf.ports = Some(new_ports);
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct OvsBridgeConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Only validate for applying, when set to `true`, extra OVS patch ports
    /// will not fail the verification. Default is false.
    /// This property will not be persisted, every time you modify
    /// ports of specified OVS bridge, you need to explicitly define this
    /// property if not using default value.
    /// Deserialize from `allow-extra-patch-ports`.
    pub allow_extra_patch_ports: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<OvsBridgeOptions>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "port",
        alias = "ports"
    )]
    /// Serialize to 'port'. Deserialize from `port` or `ports` or
    /// `slaves`(deprecated).
    pub ports: Option<Vec<OvsBridgePortConfig>>,
    // Deprecated, please use `ports`, this is only for backwards compatibility
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "port",
        alias = "slaves"
    )]
    pub(crate) slaves: Option<Vec<OvsBridgePortConfig>>,
}

impl OvsBridgeConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn post_deserialize_cleanup(&mut self) {
        if self.slaves.as_ref().is_some() {
            log::warn!(
                "The `slaves` is deprecated, please replace with `ports`."
            );
            self.ports = self.slaves.clone();
            self.slaves = None;
        }
    }

    pub(crate) fn sanitize(
        &mut self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if let Some(port_confs) = self.ports.as_ref() {
            for port_conf in port_confs {
                if let Some(vlan_conf) = port_conf.vlan.as_ref() {
                    vlan_conf.sanitize(is_desired)?;
                }
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct OvsBridgeOptions {
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "ovs_stp_deserializer"
    )]
    pub stp: Option<OvsBridgeStpOptions>,
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
    // OVS DPDK `n_rxq_desc` and `n_txq_desc` should be power of 2 within
    // 1-4096.
    pub(crate) fn sanitize(
        &self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if is_desired && self.patch.is_some() {
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
        if let Some(dpdk_conf) = self.dpdk.as_ref() {
            dpdk_conf.sanitize(is_desired)?;
        }
        Ok(())
    }

    pub(crate) fn is_ovs_patch_port(&self) -> bool {
        self.patch.is_some()
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
    #[serde(skip_serializing_if = "Option::is_none", rename = "ovs-db")]
    /// OpenvSwitch specific `other_config` for OVS bond. Please refer to
    /// manpage `ovs-vswitchd.conf.db(5)` for more detail.
    /// When setting to None, nmstate will try to preserve current
    /// `other_config`, otherwise, nmstate will override all `other_config`
    /// for specified OVS bond.
    pub ovsdb: Option<OvsDbIfaceConfig>,
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
#[serde(deny_unknown_fields)]
#[non_exhaustive]
pub struct OvsDpdkConfig {
    pub devargs: String,
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "n_rxq",
        rename = "rx-queue"
    )]
    /// Deserialize and serialize from/to `rx-queue`. You may also use
    /// OVS terminology `n_rxq` for this property.
    pub rx_queue: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Specifies  the  rx  queue  size (number rx descriptors) for dpdk ports.
    /// Must be power of 2 in the range of 1 to 4096.
    /// Setting to 0 means remove this setting from OVS database.
    pub n_rxq_desc: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Specifies  the  tx  queue  size (number tx descriptors) for dpdk ports.
    /// Must be power of 2 in the range of 1 to 4096.
    /// Setting to 0 means remove this setting from OVS database.
    pub n_txq_desc: Option<u32>,
}

const POWER_2_BETWEEN_1_4096: [u32; 13] =
    [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096];

fn validate_dpdk_queue_desc(
    n: u32,
    prop_name: &str,
) -> Result<(), NmstateError> {
    if n != 0 && !POWER_2_BETWEEN_1_4096.contains(&n) {
        Err(NmstateError::new(
            ErrorKind::InvalidArgument,
            format!(
                "OVS DPDK {prop_name} must power of 2 within \
                range of 1 to 4096. Setting to 0 if you want to remove \
                this setting from OVS database. But got {n}"
            ),
        ))
    } else {
        Ok(())
    }
}

impl OvsDpdkConfig {
    pub(crate) fn sanitize(
        &self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if is_desired {
            if let Some(n_rxq_desc) = self.n_rxq_desc {
                validate_dpdk_queue_desc(n_rxq_desc, "n_rxq_desc")?;
            }
            if let Some(n_txq_desc) = self.n_txq_desc {
                validate_dpdk_queue_desc(n_txq_desc, "n_txq_desc")?;
            }
        }
        Ok(())
    }
}

impl MergedInterface {
    // Since OVS Bridge cannot live without port, when user desire empty
    // OVS bridge, we add a OVS internal interface using the same name as the
    // OVS bridge.
    pub(crate) fn create_ovs_iface_for_empty_ports(&mut self) {
        if self.is_desired()
            && self.merged.iface_type() == InterfaceType::OvsBridge
            && self.merged.ports().map(|p| p.is_empty()).unwrap_or(true)
        {
            log::warn!(
                "OVS bridge {} cannot exist with empty port list, adding a \
                OVS internal interface with the same name",
                self.merged.name()
            );
            let iface_name = self.merged.name().to_string();

            if let (
                Some(Interface::OvsBridge(verify_iface)),
                Some(Interface::OvsBridge(apply_iface)),
                Interface::OvsBridge(merged_iface),
                Some(Interface::OvsBridge(des_iface)),
            ) = (
                self.for_verify.as_mut(),
                self.for_apply.as_mut(),
                &mut self.merged,
                &mut self.desired,
            ) {
                let port_confs = vec![OvsBridgePortConfig {
                    name: iface_name,
                    ..Default::default()
                }];

                if let Some(br_conf) = merged_iface.bridge.as_mut() {
                    br_conf.ports = Some(port_confs.clone());
                } else {
                    merged_iface.bridge = Some(OvsBridgeConfig {
                        ports: Some(port_confs.clone()),
                        ..Default::default()
                    })
                }

                if let Some(br_conf) = apply_iface.bridge.as_mut() {
                    br_conf.ports = Some(port_confs.clone());
                } else {
                    apply_iface.bridge = Some(OvsBridgeConfig {
                        ports: Some(port_confs.clone()),
                        ..Default::default()
                    })
                }

                if let Some(br_conf) = des_iface.bridge.as_mut() {
                    br_conf.ports = Some(port_confs.clone());
                } else {
                    des_iface.bridge = Some(OvsBridgeConfig {
                        ports: Some(port_confs.clone()),
                        ..Default::default()
                    })
                }

                if let Some(br_conf) = verify_iface.bridge.as_mut() {
                    if br_conf.ports.is_some() {
                        br_conf.ports = Some(port_confs);
                    }
                }
            }
        }
    }
}

impl MergedInterfaces {
    // This function remove extra(undesired) ovs patch port from pre-apply
    // current, so it will not interfere with port change.
    pub(crate) fn process_allow_extra_ovs_patch_ports_for_apply(&mut self) {
        let mut ovs_patch_port_names: HashSet<String> = HashSet::new();
        for cur_iface in self.iter().filter_map(|i| {
            if let Some(Interface::OvsInterface(o)) = i.current.as_ref() {
                Some(o)
            } else {
                None
            }
        }) {
            if cur_iface.is_ovs_patch_port() {
                ovs_patch_port_names.insert(cur_iface.base.name.to_string());
            }
        }

        for merged_iface in self.iter_mut().filter(|i| {
            if let Some(Interface::OvsBridge(o)) = i.desired.as_ref() {
                o.base.state == InterfaceState::Up
                    && o.bridge.as_ref().and_then(|c| c.allow_extra_patch_ports)
                        == Some(true)
            } else {
                false
            }
        }) {
            if let (Some(des_iface), Some(cur_iface)) =
                (merged_iface.desired.as_ref(), merged_iface.current.as_mut())
            {
                let mut ports_to_delete: HashSet<String> = HashSet::new();
                if let (Some(des_ports), Some(cur_ports)) =
                    (des_iface.ports(), cur_iface.ports())
                {
                    for cur_port_name in cur_ports {
                        if ovs_patch_port_names.contains(cur_port_name)
                            && !des_ports.contains(&cur_port_name)
                        {
                            ports_to_delete.insert(cur_port_name.to_string());
                        }
                    }
                }
                for port_name in ports_to_delete.iter() {
                    cur_iface.remove_port(port_name);
                }
            }
        }
    }
}

pub type OvsBridgeStpOptions = LinuxBridgeStpOptions;

impl OvsBridgeStpOptions {
    pub(crate) fn new_enabled(enabled: bool) -> Self {
        Self {
            enabled: Some(enabled),
            ..Default::default()
        }
    }
}

pub(crate) fn ovs_stp_deserializer<'de, D>(
    deserializer: D,
) -> Result<Option<OvsBridgeStpOptions>, D::Error>
where
    D: Deserializer<'de>,
{
    let v = serde_json::Value::deserialize(deserializer)?;

    match v {
        serde_json::Value::Bool(enabled) => {
            Ok(Some(OvsBridgeStpOptions::new_enabled(enabled)))
        }
        serde_json::Value::String(v) => match v.to_lowercase().as_str() {
            "1" | "true" | "yes" | "on" | "y" => {
                Ok(Some(OvsBridgeStpOptions::new_enabled(true)))
            }
            "0" | "false" | "no" | "off" | "n" => {
                Ok(Some(OvsBridgeStpOptions::new_enabled(true)))
            }
            _ => Err(de::Error::custom(
                "Need to be boolean: 1|0|true|false|yes|no|on|off|y|n",
            )),
        },
        serde_json::Value::Object(_) => Ok(Some(
            OvsBridgeStpOptions::deserialize(v)
                .map_err(serde::de::Error::custom)?,
        )),
        _ => Err(de::Error::custom(
            "Need to be boolean or map like {enabled: true}",
        )),
    }
}
