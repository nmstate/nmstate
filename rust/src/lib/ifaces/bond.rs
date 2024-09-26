// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde::{
    de::IntoDeserializer, Deserialize, Deserializer, Serialize, Serializer,
};

use crate::{
    deserializer::NumberAsString, BaseInterface, ErrorKind, Interface,
    InterfaceState, InterfaceType, MergedInterface, NmstateError,
};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
/// Bond interface.
///
/// When serializing or deserializing, the [BaseInterface] will
/// be flatted and [BondConfig] stored as `link-aggregation` section. The yaml
/// output [crate::NetworkState] containing an example bond interface:
/// ```yml
/// interfaces:
/// - name: bond99
///   type: bond
///   state: up
///   mac-address: 1A:24:D5:CA:76:54
///   mtu: 1500
///   min-mtu: 68
///   max-mtu: 65535
///   wait-ip: any
///   ipv4:
///     enabled: false
///   ipv6:
///     enabled: false
///   accept-all-mac-addresses: false
///   link-aggregation:
///     mode: balance-rr
///     options:
///       all_slaves_active: dropped
///       arp_all_targets: any
///       arp_interval: 0
///       arp_validate: none
///       downdelay: 0
///       lp_interval: 1
///       miimon: 100
///       min_links: 0
///       packets_per_slave: 1
///       primary_reselect: always
///       resend_igmp: 1
///       updelay: 0
///       use_carrier: true
///     port:
///     - eth1
///     - eth2
/// ```
pub struct BondInterface {
    #[serde(flatten)]
    /// Base interface. Flat during serializing.
    pub base: BaseInterface,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "link-aggregation"
    )]
    /// Bond specific settings.
    pub bond: Option<BondConfig>,
}

impl Default for BondInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::Bond;
        Self { base, bond: None }
    }
}

impl BondInterface {
    // * Do not merge bond options from current when bond mode is changing
    pub(crate) fn special_merge(&mut self, desired: &Self, current: &Self) {
        if let Some(bond_conf) = self.bond.as_mut() {
            if let (Some(des_bond_conf), Some(cur_bond_conf)) =
                (desired.bond.as_ref(), current.bond.as_ref())
            {
                if des_bond_conf.mode != cur_bond_conf.mode {
                    bond_conf.options.clone_from(&des_bond_conf.options);
                }
            }
        }
    }

    fn drop_empty_arp_ip_target(&mut self) {
        if let Some(ref mut bond_conf) = self.bond {
            if let Some(ref mut bond_opts) = &mut bond_conf.options {
                if let Some(ref mut arp_ip_target) = bond_opts.arp_ip_target {
                    if arp_ip_target.is_empty() {
                        bond_opts.arp_ip_target = None;
                    }
                }
            }
        }
    }

    fn sort_ports(&mut self) {
        if let Some(ref mut bond_conf) = self.bond {
            if let Some(ref mut port_conf) = &mut bond_conf.port {
                port_conf.sort_unstable_by_key(|p| p.clone())
            }
        }
    }

    fn sort_ports_config(&mut self) {
        if let Some(ref mut bond_conf) = self.bond {
            if let Some(ref mut port_conf) = &mut bond_conf.ports_config {
                port_conf.sort_unstable_by_key(|p| p.name.clone())
            }
        }
    }

    pub(crate) fn sanitize(&mut self) -> Result<(), NmstateError> {
        self.sort_ports();
        self.sort_ports_config();
        self.drop_empty_arp_ip_target();
        self.make_ad_actor_system_mac_upper_case();
        self.check_overlap_queue_id()?;
        Ok(())
    }

    // In kernel code drivers/net/bonding/bond_options.c
    // bond_option_queue_id_set(), kernel is not allowing multiple bond port
    // holding the same queue ID, hence we raise error when queue id overlapped.
    fn check_overlap_queue_id(&self) -> Result<(), NmstateError> {
        let mut existing_qids: HashMap<u16, &str> = HashMap::new();
        if let Some(ports_conf) =
            self.bond.as_ref().and_then(|b| b.ports_config.as_deref())
        {
            for port_conf in ports_conf
                .iter()
                .filter(|p| p.queue_id.is_some() && p.queue_id != Some(0))
            {
                if let Some(queue_id) = port_conf.queue_id {
                    if let Some(exist_port_name) = existing_qids.get(&queue_id)
                    {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Port {} and {} of Bond {} are sharing the \
                                same queue-id which is not supported by \
                                linux kernel yet",
                                exist_port_name,
                                port_conf.name.as_str(),
                                self.base.name.as_str()
                            ),
                        ));
                    } else {
                        existing_qids.insert(queue_id, port_conf.name.as_str());
                    }
                }
            }
        }
        Ok(())
    }

    // Return None when desire state does not mention ports
    pub(crate) fn ports(&self) -> Option<Vec<&str>> {
        let config = self.bond.clone().unwrap_or_default();
        if config.port.is_some() {
            self.bond
                .as_ref()
                .and_then(|bond_conf| bond_conf.port.as_ref())
                .map(|ports| {
                    ports.as_slice().iter().map(|p| p.as_str()).collect()
                })
        } else {
            self.bond
                .as_ref()
                .and_then(|bond_conf| bond_conf.ports_config.as_ref())
                .map(|ports| {
                    ports.as_slice().iter().map(|p| p.name.as_str()).collect()
                })
        }
    }

    pub(crate) fn get_port_conf(
        &self,
        port_name: &str,
    ) -> Option<&BondPortConfig> {
        self.bond
            .as_ref()
            .and_then(|bond_conf| bond_conf.ports_config.as_ref())
            .and_then(|port_confs| {
                port_confs
                    .iter()
                    .find(|port_conf| port_conf.name == port_name)
            })
    }

    pub(crate) fn mode(&self) -> Option<BondMode> {
        self.bond.as_ref().and_then(|bond_conf| bond_conf.mode)
    }

    pub fn new() -> Self {
        Self::default()
    }

    fn is_mac_restricted_mode(&self) -> bool {
        self.bond
            .as_ref()
            .and_then(|bond_conf| {
                if self.mode() == Some(BondMode::ActiveBackup) {
                    bond_conf.options.as_ref()
                } else {
                    None
                }
            })
            .and_then(|bond_opts| bond_opts.fail_over_mac)
            == Some(BondFailOverMac::Active)
    }

    fn is_not_mac_restricted_mode_explicitly(&self) -> bool {
        (self.mode().is_some() && self.mode() != Some(BondMode::ActiveBackup))
            || ![None, Some(BondFailOverMac::Active)].contains(
                &self
                    .bond
                    .as_ref()
                    .and_then(|bond_conf| bond_conf.options.as_ref())
                    .and_then(|bond_opts| bond_opts.fail_over_mac),
            )
    }

    fn validate_new_iface_with_no_mode(
        &self,
        current: Option<&Interface>,
    ) -> Result<(), NmstateError> {
        if self.base.state == InterfaceState::Up
            && current.is_none()
            && self.mode().is_none()
        {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Bond mode is mandatory for new bond interface: {}",
                    &self.base.name
                ),
            );
            log::error!("{}", e);
            return Err(e);
        }
        Ok(())
    }

    // Fail on
    // * Desire mac restricted mode with mac defined
    // * Desire mac address with current interface in mac restricted mode with
    //   desired not changing mac restricted mode
    fn validate_mac_restricted_mode(
        &self,
        current: Option<&Interface>,
    ) -> Result<(), NmstateError> {
        let e = NmstateError::new(
            ErrorKind::InvalidArgument,
            "MAC address cannot be specified in bond interface along with \
            fail_over_mac active on active backup mode"
                .to_string(),
        );
        if self.is_mac_restricted_mode() && self.base.mac_address.is_some() {
            log::error!("{}", e);
            return Err(e);
        }

        if let Some(Interface::Bond(current)) = current {
            if current.is_mac_restricted_mode()
                && self.base.mac_address.is_some()
                && !self.is_not_mac_restricted_mode_explicitly()
            {
                log::error!("{}", e);
                return Err(e);
            }
        }
        Ok(())
    }

    fn validate_conflict_in_port_and_port_configs(
        &self,
    ) -> Result<(), NmstateError> {
        let bond_config = self.bond.clone().unwrap_or_default();
        if bond_config.port.is_some() && bond_config.ports_config.is_some() {
            let mut port_list = bond_config.port.unwrap_or_default();
            let mut port_config_list: Vec<String> = bond_config
                .ports_config
                .unwrap_or_default()
                .into_iter()
                .map(|p| p.name)
                .collect();
            port_list.sort_unstable();
            port_config_list.sort_unstable();
            let matching = port_list
                .iter()
                .zip(port_config_list.iter())
                .filter(|&(port_name, port_config_name)| {
                    port_name == port_config_name
                })
                .count();
            if matching != port_list.len() || matching != port_config_list.len()
            {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "The port names specified in `port` conflict with \
                        the port names specified in `ports-config` for \
                        bond interface: {}",
                        &self.base.name
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
        Ok(())
    }

    pub(crate) fn is_options_reset(&self) -> bool {
        if let Some(bond_opts) = self
            .bond
            .as_ref()
            .and_then(|bond_conf| bond_conf.options.as_ref())
        {
            bond_opts == &BondOptions::default()
        } else {
            false
        }
    }

    fn make_ad_actor_system_mac_upper_case(&mut self) {
        if let Some(mac) = self
            .bond
            .as_mut()
            .and_then(|c| c.options.as_mut())
            .and_then(|o| o.ad_actor_system.as_mut())
        {
            mac.make_ascii_uppercase();
        }
    }

    pub(crate) fn remove_port(&mut self, port_to_remove: &str) {
        if let Some(index) = self.bond.as_ref().and_then(|bond_conf| {
            bond_conf.port.as_ref().and_then(|ports| {
                ports
                    .iter()
                    .position(|port_name| port_name == port_to_remove)
            })
        }) {
            self.bond
                .as_mut()
                .and_then(|bond_conf| bond_conf.port.as_mut())
                .map(|ports| ports.remove(index));
        }
    }

    pub(crate) fn change_port_name(
        &mut self,
        origin_name: &str,
        new_name: String,
    ) {
        if let Some(index) = self
            .bond
            .as_ref()
            .and_then(|bond_conf| bond_conf.port.as_ref())
            .and_then(|ports| {
                ports.iter().position(|port_name| port_name == origin_name)
            })
        {
            if let Some(ports) = self
                .bond
                .as_mut()
                .and_then(|bond_conf| bond_conf.port.as_mut())
            {
                ports[index] = new_name;
            }
        }
    }

    pub(crate) fn get_config_changed_ports(&self, current: &Self) -> Vec<&str> {
        let mut ret: Vec<&str> = Vec::new();
        let mut des_ports_index: HashMap<&str, &BondPortConfig> =
            HashMap::new();
        let mut cur_ports_index: HashMap<&str, &BondPortConfig> =
            HashMap::new();
        if let Some(port_confs) = self
            .bond
            .as_ref()
            .and_then(|bond_conf| bond_conf.ports_config.as_ref())
        {
            for port_conf in port_confs {
                des_ports_index.insert(port_conf.name.as_str(), port_conf);
            }
        }

        if let Some(port_confs) = current
            .bond
            .as_ref()
            .and_then(|bond_conf| bond_conf.ports_config.as_ref())
        {
            for port_conf in port_confs {
                cur_ports_index.insert(port_conf.name.as_str(), port_conf);
            }
        }

        for (port_name, port_conf) in des_ports_index.iter() {
            if let Some(cur_port_conf) = cur_ports_index.get(port_name) {
                if port_conf.is_changed(cur_port_conf) {
                    ret.push(port_name);
                }
            }
        }
        ret
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[non_exhaustive]
#[serde(remote = "BondMode")]
/// Bond mode
pub enum BondMode {
    #[serde(rename = "balance-rr", alias = "0")]
    /// Deserialize and serialize from/to `balance-rr`.
    /// You can use integer 0 for deserializing to this mode.
    RoundRobin,
    #[serde(rename = "active-backup", alias = "1")]
    /// Deserialize and serialize from/to `active-backup`.
    /// You can use integer 1 for deserializing to this mode.
    ActiveBackup,
    #[serde(rename = "balance-xor", alias = "2")]
    /// Deserialize and serialize from/to `balance-xor`.
    /// You can use integer 2 for deserializing to this mode.
    XOR,
    #[serde(rename = "broadcast", alias = "3")]
    /// Deserialize and serialize from/to `broadcast`.
    /// You can use integer 3 for deserializing to this mode.
    Broadcast,
    #[serde(rename = "802.3ad", alias = "4")]
    /// Deserialize and serialize from/to `802.3ad`.
    /// You can use integer 4 for deserializing to this mode.
    LACP,
    #[serde(rename = "balance-tlb", alias = "5")]
    /// Deserialize and serialize from/to `balance-tlb`.
    /// You can use integer 5 for deserializing to this mode.
    TLB,
    /// Deserialize and serialize from/to `balance-alb`.
    /// You can use integer 6 for deserializing to this mode.
    #[serde(rename = "balance-alb", alias = "6")]
    ALB,
    #[serde(rename = "unknown")]
    Unknown,
}

impl<'de> Deserialize<'de> for BondMode {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        BondMode::deserialize(
            NumberAsString::deserialize(deserializer)?
                .as_str()
                .into_deserializer(),
        )
    }
}

impl Serialize for BondMode {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        BondMode::serialize(self, serializer)
    }
}

impl Default for BondMode {
    fn default() -> Self {
        Self::RoundRobin
    }
}

impl std::fmt::Display for BondMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                BondMode::RoundRobin => "balance-rr",
                BondMode::ActiveBackup => "active-backup",
                BondMode::XOR => "balance-xor",
                BondMode::Broadcast => "broadcast",
                BondMode::LACP => "802.3ad",
                BondMode::TLB => "balance-tlb",
                BondMode::ALB => "balance-alb",
                BondMode::Unknown => "unknown",
            }
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct BondConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Mode is mandatory when create new bond interface.
    pub mode: Option<BondMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// When applying, if defined, it will override current port list.
    /// The verification will not fail on bond options miss-match but an
    /// warning message.
    /// Please refer to [kernel documentation](https://www.kernel.org/doc/Documentation/networking/bonding.txt) for detail
    pub options: Option<BondOptions>,
    #[serde(skip_serializing_if = "Option::is_none", alias = "ports")]
    /// Deserialize and serialize from/to `port`.
    /// You can also use `ports` for deserializing.
    /// When applying, if defined, it will override current port list.
    pub port: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Deserialize and serialize from/to `ports-config`.
    /// When applying, if defined, it will override current ports
    /// configuration. Note that `port` is not required to set with
    /// `ports-config`. An error will be raised during apply when the port
    /// names specified in `port` and `ports-config` conflict with each
    /// other.
    pub ports_config: Option<Vec<BondPortConfig>>,
}

impl BondConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[non_exhaustive]
#[serde(remote = "BondAdSelect", rename_all = "kebab-case")]
/// Specifies the 802.3ad aggregation selection logic to use.
pub enum BondAdSelect {
    /// Deserialize and serialize from/to `stable`.
    #[serde(alias = "0")]
    Stable,
    /// Deserialize and serialize from/to `bandwidth`.
    #[serde(alias = "1")]
    Bandwidth,
    /// Deserialize and serialize from/to `count`.
    #[serde(alias = "2")]
    Count,
}

impl<'de> Deserialize<'de> for BondAdSelect {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        BondAdSelect::deserialize(
            NumberAsString::deserialize(deserializer)?
                .as_str()
                .into_deserializer(),
        )
    }
}

impl Serialize for BondAdSelect {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        BondAdSelect::serialize(self, serializer)
    }
}

impl std::fmt::Display for BondAdSelect {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Stable => "stable",
                Self::Bandwidth => "bandwidth",
                Self::Count => "count",
            }
        )
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone)]
#[serde(rename_all = "kebab-case", remote = "BondLacpRate")]
#[non_exhaustive]
/// Option specifying the rate in which we'll ask our link partner to transmit
/// LACPDU packets in 802.3ad mode
pub enum BondLacpRate {
    /// Request partner to transmit LACPDUs every 30 seconds.
    /// Serialize to `slow`.
    /// Deserialize from 0 or `slow`.
    #[serde(alias = "0")]
    Slow,
    /// Request partner to transmit LACPDUs every 1 second
    /// Serialize to `fast`.
    /// Deserialize from 1 or `fast`.
    #[serde(alias = "1")]
    Fast,
}

impl<'de> Deserialize<'de> for BondLacpRate {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        BondLacpRate::deserialize(
            NumberAsString::deserialize(deserializer)?
                .as_str()
                .into_deserializer(),
        )
    }
}

impl Serialize for BondLacpRate {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        BondLacpRate::serialize(self, serializer)
    }
}

impl std::fmt::Display for BondLacpRate {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Slow => "slow",
                Self::Fast => "fast",
            }
        )
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[serde(rename_all = "kebab-case", remote = "BondAllPortsActive")]
#[non_exhaustive]
/// Equal to kernel `all_slaves_active` option.
/// Specifies that duplicate frames (received on inactive ports) should be
/// dropped (0) or delivered (1).
pub enum BondAllPortsActive {
    /// Drop the duplicate frames
    /// Serialize to `dropped`.
    /// Deserialize from 0 or `dropped`.
    #[serde(alias = "0")]
    Dropped,
    /// Deliver the duplicate frames
    /// Serialize to `delivered`.
    /// Deserialize from 1 or `delivered`.
    #[serde(alias = "1")]
    Delivered,
}

impl<'de> Deserialize<'de> for BondAllPortsActive {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        BondAllPortsActive::deserialize(
            NumberAsString::deserialize(deserializer)?
                .as_str()
                .into_deserializer(),
        )
    }
}

impl Serialize for BondAllPortsActive {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        BondAllPortsActive::serialize(self, serializer)
    }
}

impl std::fmt::Display for BondAllPortsActive {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Dropped => "dropped",
                Self::Delivered => "delivered",
            }
        )
    }
}

impl From<BondAllPortsActive> for u8 {
    fn from(v: BondAllPortsActive) -> u8 {
        match v {
            BondAllPortsActive::Dropped => 0,
            BondAllPortsActive::Delivered => 1,
        }
    }
}

/// The `arp_all_targets` kernel bond option.
///
/// Specifies the quantity of arp_ip_targets that must be reachable in order for
/// the ARP monitor to consider a port as being up. This option affects only
/// active-backup mode for ports with arp_validation enabled.
#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone)]
#[serde(rename_all = "kebab-case", remote = "BondArpAllTargets")]
#[non_exhaustive]
pub enum BondArpAllTargets {
    /// consider the port up only when any of the `arp_ip_targets` is reachable
    #[serde(alias = "0")]
    Any,
    /// consider the port up only when all of the `arp_ip_targets` are
    /// reachable
    #[serde(alias = "1")]
    All,
}

impl<'de> Deserialize<'de> for BondArpAllTargets {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        BondArpAllTargets::deserialize(
            NumberAsString::deserialize(deserializer)?
                .as_str()
                .into_deserializer(),
        )
    }
}

impl Serialize for BondArpAllTargets {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        BondArpAllTargets::serialize(self, serializer)
    }
}

impl std::fmt::Display for BondArpAllTargets {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Any => "any",
                Self::All => "all",
            }
        )
    }
}

/// The `arp_validate` kernel bond option.
///
/// Specifies whether or not ARP probes and replies should be validated in any
/// mode that supports arp monitoring, or whether non-ARP traffic should be
/// filtered (disregarded) for link monitoring purposes.
#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone)]
#[serde(rename_all = "snake_case", remote = "BondArpValidate")]
#[non_exhaustive]
pub enum BondArpValidate {
    /// No validation or filtering is performed.
    /// Serialize to `none`.
    /// Deserialize from 0 or `none`.
    #[serde(alias = "0")]
    None,
    /// Validation is performed only for the active port.
    /// Serialize to `active`.
    /// Deserialize from 1 or `active`.
    #[serde(alias = "1")]
    Active,
    /// Validation is performed only for backup ports.
    /// Serialize to `backup`.
    /// Deserialize from 2 or `backup`.
    #[serde(alias = "2")]
    Backup,
    /// Validation is performed for all ports.
    /// Serialize to `all`.
    /// Deserialize from 3 or `all`.
    #[serde(alias = "3")]
    All,
    /// Filtering is applied to all ports. No validation is performed.
    /// Serialize to `filter`.
    /// Deserialize from 4 or `filter`.
    #[serde(alias = "4")]
    Filter,
    /// Filtering is applied to all ports, validation is performed only for
    /// the active port.
    /// Serialize to `filter_active`.
    /// Deserialize from 5 or `filter-active`.
    #[serde(alias = "5")]
    FilterActive,
    /// Filtering is applied to all ports, validation is performed only for
    /// backup port.
    /// Serialize to `filter_backup`.
    /// Deserialize from 6 or `filter_backup`.
    #[serde(alias = "6")]
    FilterBackup,
}

impl<'de> Deserialize<'de> for BondArpValidate {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        BondArpValidate::deserialize(
            NumberAsString::deserialize(deserializer)?
                .as_str()
                .into_deserializer(),
        )
    }
}

impl Serialize for BondArpValidate {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        BondArpValidate::serialize(self, serializer)
    }
}

impl std::fmt::Display for BondArpValidate {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::None => "none",
                Self::Active => "active",
                Self::Backup => "backup",
                Self::All => "all",
                Self::Filter => "filter",
                Self::FilterActive => "filter_active",
                Self::FilterBackup => "filter_backup",
            }
        )
    }
}

/// The `fail_over_mac` kernel bond option.
///
/// Specifies whether active-backup mode should set all ports to the same MAC
/// address at port attachment (the traditional behavior), or, when enabled,
/// perform special handling of the bond's MAC address in accordance with the
/// selected policy.
#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[serde(rename_all = "kebab-case", remote = "BondFailOverMac")]
#[non_exhaustive]
pub enum BondFailOverMac {
    /// This setting disables fail_over_mac, and causes bonding to set all
    /// ports of an active-backup bond to the same MAC address at attachment
    /// time.
    /// Serialize to `none`.
    /// Deserialize from 0 or `none`.
    #[serde(alias = "0")]
    None,
    /// The "active" fail_over_mac policy indicates that the MAC address of the
    /// bond should always be the MAC address of the currently active port.
    /// The MAC address of the ports is not changed; instead, the MAC address
    /// of the bond changes during a failover.
    /// Serialize to `active`.
    /// Deserialize from 1 or `active`.
    #[serde(alias = "1")]
    Active,
    /// The "follow" fail_over_mac policy causes the MAC address of the bond to
    /// be selected normally (normally the MAC address of the first port added
    /// to the bond). However, the second and subsequent ports are not set to
    /// this MAC address while they are in a backup role; a port is programmed
    /// with the bond's MAC address at failover time (and the formerly active
    /// port receives the newly active port's MAC address).
    /// Serialize to `follow`.
    /// Deserialize from 2 or `follow`.
    #[serde(alias = "2")]
    Follow,
}

impl<'de> Deserialize<'de> for BondFailOverMac {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        BondFailOverMac::deserialize(
            NumberAsString::deserialize(deserializer)?
                .as_str()
                .into_deserializer(),
        )
    }
}

impl Serialize for BondFailOverMac {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        BondFailOverMac::serialize(self, serializer)
    }
}

impl std::fmt::Display for BondFailOverMac {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::None => "none",
                Self::Active => "active",
                Self::Follow => "follow",
            }
        )
    }
}

/// The `primary_reselect` kernel bond option.
///
/// Specifies the reselection policy for the primary port. This affects how the
/// primary port is chosen to become the active port when failure of the active
/// port or recovery of the primary port occurs. This option is designed to
/// prevent flip-flopping between the primary port and other ports.
#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone)]
#[serde(rename_all = "kebab-case", remote = "BondPrimaryReselect")]
#[non_exhaustive]
pub enum BondPrimaryReselect {
    ///The primary port becomes the active port whenever it comes back up.
    /// Serialize to `always`.
    /// Deserialize from 0 or `always`.
    #[serde(alias = "0")]
    Always,
    /// The primary port becomes the active port when it comes back up, if the
    /// speed and duplex of the primary port is better than the speed and
    /// duplex of the current active port.
    /// Serialize to `better`.
    /// Deserialize from 1 or `better`.
    #[serde(alias = "1")]
    Better,
    /// The primary port becomes the active port only if the current active
    /// port fails and the primary port is up.
    /// Serialize to `failure`.
    /// Deserialize from 2 or `failure`.
    #[serde(alias = "2")]
    Failure,
}

impl<'de> Deserialize<'de> for BondPrimaryReselect {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        BondPrimaryReselect::deserialize(
            NumberAsString::deserialize(deserializer)?
                .as_str()
                .into_deserializer(),
        )
    }
}

impl Serialize for BondPrimaryReselect {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        BondPrimaryReselect::serialize(self, serializer)
    }
}
impl std::fmt::Display for BondPrimaryReselect {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Always => "always",
                Self::Better => "better",
                Self::Failure => "failure",
            }
        )
    }
}

/// The `xmit_hash_policy` kernel bond option.
///
/// Selects the transmit hash policy to use for port selection in balance-xor,
/// 802.3ad, and tlb modes.
#[derive(Deserialize, Serialize, Debug, PartialEq, Eq, Clone, Copy)]
#[non_exhaustive]
#[serde(remote = "BondXmitHashPolicy")]
pub enum BondXmitHashPolicy {
    #[serde(rename = "layer2", alias = "0")]
    /// Serialize to `layer2`.
    /// Deserialize from 0 or `layer2`.
    Layer2,
    #[serde(rename = "layer3+4", alias = "1")]
    /// Serialize to `layer3+4`.
    /// Deserialize from 1 or `layer3+4`.
    Layer34,
    #[serde(rename = "layer2+3", alias = "2")]
    /// Serialize to `layer2+3`.
    /// Deserialize from 2 or `layer2+3`.
    Layer23,
    #[serde(rename = "encap2+3", alias = "3")]
    /// Serialize to `encap2+3`.
    /// Deserialize from 3 or `encap2+3`.
    Encap23,
    #[serde(rename = "encap3+4", alias = "4")]
    /// Serialize to `encap3+4`.
    /// Deserialize from 4 or `encap3+4`.
    Encap34,
    #[serde(rename = "vlan+srcmac", alias = "5")]
    /// Serialize to `vlan+srcmac`.
    /// Deserialize from 5 or `vlan+srcmac`.
    VlanSrcMac,
}

impl<'de> Deserialize<'de> for BondXmitHashPolicy {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        BondXmitHashPolicy::deserialize(
            NumberAsString::deserialize(deserializer)?
                .as_str()
                .into_deserializer(),
        )
    }
}

impl Serialize for BondXmitHashPolicy {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        BondXmitHashPolicy::serialize(self, serializer)
    }
}

impl std::fmt::Display for BondXmitHashPolicy {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Layer2 => "layer2",
                Self::Layer34 => "layer3+4",
                Self::Layer23 => "layer2+3",
                Self::Encap23 => "encap2+3",
                Self::Encap34 => "encap3+4",
                Self::VlanSrcMac => "vlan+srcmac",
            }
        )
    }
}

#[derive(Debug, Serialize, Deserialize, Default, Clone, PartialEq, Eq)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
pub struct BondOptions {
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u16_or_string"
    )]
    /// In an AD system, this specifies the system priority. The allowed range
    /// is 1 - 65535.
    pub ad_actor_sys_prio: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// In an AD system, this specifies the mac-address for the actor in
    /// protocol packet exchanges (LACPDUs). The value cannot be NULL or
    /// multicast. It is preferred to have the local-admin bit set for this mac
    /// but driver does not enforce it. If the value is not given then system
    /// defaults to using the controller's mac address as actors' system
    /// address.
    pub ad_actor_system: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Specifies the 802.3ad aggregation selection logic to use. The
    /// possible values and their effects are:
    pub ad_select: Option<BondAdSelect>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u16_or_string"
    )]
    /// In an AD system, the port-key has three parts as shown below -
    ///
    /// ```text
    /// Bits   Use
    /// 00     Duplex
    /// 01-05  Speed
    /// 06-15  User-defined
    /// ```
    ///
    /// This defines the upper 10 bits of the port key. The values can be from
    /// 0
    /// - 1023. If not given, the system defaults to 0.
    ///
    /// This parameter has effect only in 802.3ad mode.
    pub ad_user_port_key: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Specifies that duplicate frames (received on inactive ports) should be
    /// dropped (0) or delivered (1).
    ///
    /// Normally, bonding will drop duplicate frames (received on inactive
    /// ports), which is desirable for most users. But there are some times it
    /// is nice to allow duplicate frames to be delivered.
    pub all_slaves_active: Option<BondAllPortsActive>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Specifies the quantity of arp_ip_targets that must be reachable in
    /// order for the ARP monitor to consider a port as being up. This
    /// option affects only active-backup mode for ports with
    /// arp_validation enabled.
    pub arp_all_targets: Option<BondArpAllTargets>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Specifies the ARP link monitoring frequency in milliseconds.
    ///
    /// The ARP monitor works by periodically checking the port devices to
    /// determine whether they have sent or received traffic recently (the
    /// precise criteria depends upon the bonding mode, and the state of the
    /// port). Regular traffic is generated via ARP probes issued for the
    /// addresses specified by the arp_ip_target option.
    ///
    /// This behavior can be modified by the arp_validate option,
    /// below.
    ///
    /// If ARP monitoring is used in an etherchannel compatible mode (modes 0
    /// and 2), the switch should be configured in a mode that evenly
    /// distributes packets across all links. If the switch is configured to
    /// distribute the packets in an XOR fashion, all replies from the ARP
    /// targets will be received on the same link which could cause the other
    /// team members to fail. ARP monitoring should not be used in conjunction
    /// with miimon. A value of 0 disables ARP monitoring. The default value
    /// is 0.
    pub arp_interval: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Specifies the IP addresses to use as ARP monitoring peers when
    /// arp_interval is > 0. These are the targets of the ARP request sent to
    /// determine the health of the link to the targets. Specify these values
    /// in ddd.ddd.ddd.ddd format. Multiple IP addresses must be separated by a
    /// comma. At least one IP address must be given for ARP monitoring to
    /// function. The maximum number of targets that can be specified is 16.
    /// The default value is no IP addresses.
    pub arp_ip_target: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Specifies whether or not ARP probes and replies should be validated in
    /// any mode that supports arp monitoring, or whether non-ARP traffic
    /// should be filtered (disregarded) for link monitoring purposes.
    pub arp_validate: Option<BondArpValidate>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Specifies the time, in milliseconds, to wait before disabling a port
    /// after a link failure has been detected. This option is only valid for
    /// the miimon link monitor. The downdelay value should be a multiple of
    /// the miimon value; if not, it will be rounded down to the nearest
    /// multiple. The default value is 0.
    pub downdelay: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Specifies whether active-backup mode should set all ports to the same
    /// MAC address at enportment (the traditional behavior), or, when enabled,
    /// perform special handling of the bond's MAC address in accordance with
    /// the selected policy.
    pub fail_over_mac: Option<BondFailOverMac>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Option specifying the rate in which we'll ask our link partner to
    /// transmit LACPDU packets in 802.3ad mode.
    pub lacp_rate: Option<BondLacpRate>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Specifies the number of seconds between instances where the bonding
    /// driver sends learning packets to each slaves peer switch.
    ///
    /// The valid range is 1 - 0x7fffffff; the default value is 1. This Option
    /// has effect only in balance-tlb and balance-alb modes.
    pub lp_interval: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Specifies the MII link monitoring frequency in milliseconds.
    /// This determines how often the link state of each port is
    /// inspected for link failures. A value of zero disables MII
    /// link monitoring. A value of 100 is a good starting point.
    /// The use_carrier option, below, affects how the link state is
    /// determined. See the High Availability section for additional
    /// information. The default value is 0.
    pub miimon: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Specifies the minimum number of links that must be active before
    /// asserting carrier. It is similar to the Cisco EtherChannel min-links
    /// feature. This allows setting the minimum number of member ports that
    /// must be up (link-up state) before marking the bond device as up
    /// (carrier on). This is useful for situations where higher level services
    /// such as clustering want to ensure a minimum number of low bandwidth
    /// links are active before switchover. This option only affect 802.3ad
    /// mode.
    ///
    /// The default value is 0. This will cause carrier to be asserted (for
    /// 802.3ad mode) whenever there is an active aggregator, regardless of the
    /// number of available links in that aggregator. Note that, because an
    /// aggregator cannot be active without at least one available link,
    /// setting this option to 0 or to 1 has the exact same effect.
    pub min_links: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u8_or_string"
    )]
    /// Specify the number of peer notifications (gratuitous ARPs and
    /// unsolicited IPv6 Neighbor Advertisements) to be issued after a
    /// failover event. As soon as the link is up on the new port
    /// (possibly immediately) a peer notification is sent on the
    /// bonding device and each VLAN sub-device. This is repeated at
    /// the rate specified by peer_notif_delay if the number is
    /// greater than 1.
    ///
    /// The valid range is 0 - 255; the default value is 1. These options
    /// affect only the active-backup mode. These options were added for
    /// bonding versions 3.3.0 and 3.4.0 respectively.
    ///
    /// From Linux 3.0 and bonding version 3.7.1, these notifications are
    /// generated by the ipv4 and ipv6 code and the numbers of repetitions
    /// cannot be set independently.
    pub num_grat_arp: Option<u8>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u8_or_string"
    )]
    /// Identical to [BondOptions.num_grat_arp]
    pub num_unsol_na: Option<u8>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Specify the number of packets to transmit through a port before moving
    /// to the next one. When set to 0 then a port is chosen at random.
    ///
    /// The valid range is 0 - 65535; the default value is 1. This option has
    /// effect only in balance-rr mode.
    pub packets_per_slave: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// A string (eth0, eth2, etc) specifying which slave is the primary
    /// device. The specified device will always be the active slave while
    /// it is available. Only when the primary is off-line will alternate
    /// devices be used. This is useful when one slave is preferred over
    /// another, e.g., when one slave has higher throughput than another.
    ///
    /// The primary option is only valid for active-backup(1), balance-tlb (5)
    /// and balance-alb (6) mode.
    pub primary: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Specifies the reselection policy for the primary port. This affects
    /// how the primary port is chosen to become the active port when failure
    /// of the active port or recovery of the primary port occurs. This
    /// option is designed to prevent flip-flopping between the primary port
    /// and other ports.
    pub primary_reselect: Option<BondPrimaryReselect>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Specifies the number of IGMP membership reports to be issued after
    /// a failover event. One membership report is issued immediately after
    /// the failover, subsequent packets are sent in each 200ms interval.
    ///
    /// The valid range is 0 - 255; the default value is 1. A value of 0
    /// prevents the IGMP membership report from being issued in response
    /// to the failover event.
    ///
    /// This option is useful for bonding modes balance-rr (0), active-backup
    /// (1), balance-tlb (5) and balance-alb (6), in which a failover can
    /// switch the IGMP traffic from one port to another. Therefore a
    /// fresh IGMP report must be issued to cause the switch to forward the
    /// incoming IGMP traffic over the newly selected port.
    pub resend_igmp: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    /// Specifies if dynamic shuffling of flows is enabled in tlb mode. The
    /// value has no effect on any other modes.
    ///
    /// The default behavior of tlb mode is to shuffle active flows across
    /// ports based on the load in that interval. This gives nice lb
    /// characteristics but can cause packet reordering. If re-ordering is a
    /// concern use this variable to disable flow shuffling and rely on load
    /// balancing provided solely by the hash distribution. xmit-hash-policy
    /// can be used to select the appropriate hashing for the setup.
    ///
    /// The sysfs entry can be used to change the setting per bond device and
    /// the initial value is derived from the module parameter. The sysfs entry
    /// is allowed to be changed only if the bond device is down.
    ///
    /// The default value is "1" that enables flow shuffling while value "0"
    /// disables it. This option was added in bonding driver 3.7.1
    pub tlb_dynamic_lb: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Specifies the time, in milliseconds, to wait before enabling a port
    /// after a link recovery has been detected. This option is only valid for
    /// the miimon link monitor. The updelay value should be a multiple of the
    /// miimon value; if not, it will be rounded down to the nearest multiple.
    /// The default value is 0.
    pub updelay: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    /// Specifies whether or not miimon should use MII or ETHTOOL
    /// ioctls vs. netif_carrier_ok() to determine the link
    /// status. The MII or ETHTOOL ioctls are less efficient and
    /// utilize a deprecated calling sequence within the kernel.  The
    /// netif_carrier_ok() relies on the device driver to maintain its
    /// state with netif_carrier_on/off; at this writing, most, but
    /// not all, device drivers support this facility.
    ///
    /// If bonding insists that the link is up when it should not be,
    /// it may be that your network device driver does not support
    /// netif_carrier_on/off.  The default state for netif_carrier is
    /// "carrier on," so if a driver does not support netif_carrier,
    /// it will appear as if the link is always up.  In this case,
    /// setting use_carrier to 0 will cause bonding to revert to the
    /// MII / ETHTOOL ioctl method to determine the link state.
    ///
    /// A value of 1 enables the use of netif_carrier_ok(), a value of
    /// 0 will use the deprecated MII / ETHTOOL ioctls.  The default
    /// value is 1.
    pub use_carrier: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Selects the transmit hash policy to use for slave selection in
    /// balance-xor, 802.3ad, and tlb modes.
    pub xmit_hash_policy: Option<BondXmitHashPolicy>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string",
        alias = "balance-slb"
    )]
    pub balance_slb: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u8_or_string"
    )]
    pub arp_missed_max: Option<u8>,
}

impl BondOptions {
    pub fn new() -> Self {
        Self::default()
    }

    fn validate_ad_actor_system_mac_address(&self) -> Result<(), NmstateError> {
        if let Some(ad_actor_system) = &self.ad_actor_system {
            if ad_actor_system.to_uppercase().starts_with("01:00:5E") {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "The ad_actor_system bond option cannot be an IANA \
                    multicast address(prefix with 01:00:5E)"
                        .to_string(),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
        Ok(())
    }

    fn validate_miimon_and_arp_interval(&self) -> Result<(), NmstateError> {
        if let (Some(miimon), Some(arp_interval)) =
            (self.miimon, self.arp_interval)
        {
            if miimon > 0 && arp_interval > 0 {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Bond miimon and arp interval are not compatible options."
                        .to_string(),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
        Ok(())
    }

    fn validate_balance_slb(
        &self,
        current: Option<&Self>,
        mode: BondMode,
    ) -> Result<(), NmstateError> {
        if self
            .balance_slb
            .or_else(|| current.and_then(|c| c.balance_slb))
            == Some(true)
        {
            let xmit_hash_policy = self
                .xmit_hash_policy
                .or_else(|| current.and_then(|c| c.xmit_hash_policy));
            if mode != BondMode::XOR
                || xmit_hash_policy != Some(BondXmitHashPolicy::VlanSrcMac)
            {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "To enable balance-slb, bond mode should be \
                    balance-xor and xmit_hash_policy: 'vlan+srcmac'"
                        .to_string(),
                ));
            }
        }
        Ok(())
    }
}

impl MergedInterface {
    pub(crate) fn post_inter_ifaces_process_bond(
        &mut self,
    ) -> Result<(), NmstateError> {
        if let Some(Interface::Bond(apply_iface)) = self.for_apply.as_ref() {
            apply_iface
                .validate_new_iface_with_no_mode(self.current.as_ref())?;
            apply_iface.validate_mac_restricted_mode(self.current.as_ref())?;
            apply_iface.validate_conflict_in_port_and_port_configs()?;

            if let Some(bond_opts) =
                apply_iface.bond.as_ref().and_then(|b| b.options.as_ref())
            {
                bond_opts.validate_ad_actor_system_mac_address()?;
                bond_opts.validate_miimon_and_arp_interval()?;

                if let Interface::Bond(merged_iface) = &self.merged {
                    if let Some(mode) =
                        merged_iface.bond.as_ref().and_then(|b| b.mode)
                    {
                        let cur_bond_opts =
                            if let Some(Interface::Bond(cur_iface)) =
                                self.current.as_ref()
                            {
                                cur_iface
                                    .bond
                                    .as_ref()
                                    .and_then(|b| b.options.as_ref())
                            } else {
                                None
                            };
                        bond_opts.validate_balance_slb(cur_bond_opts, mode)?
                    }
                }
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct BondPortConfig {
    /// name is mandatory when specifying the ports configuration.
    pub name: String,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_i32_or_string"
    )]
    /// Deserialize and serialize from/to `priority`.
    /// When applying, if defined, it will override the current bond port
    /// priority. The verification will fail if bonding mode is not
    /// active-backup(1) or balance-tlb (5) or balance-alb (6).
    pub priority: Option<i32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u16_or_string"
    )]
    /// Deserialize and serialize from/to `queue-id`.
    pub queue_id: Option<u16>,
}

impl std::fmt::Display for BondPortConfig {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "BondPortConfig {{ name: {}, priority: {}, queue_id: {} }}",
            self.name,
            self.priority.unwrap_or_default(),
            self.queue_id.unwrap_or_default()
        )
    }
}

impl BondPortConfig {
    pub fn new() -> Self {
        Self::default()
    }

    fn is_changed(&self, current: &Self) -> bool {
        (self.priority.is_some() && self.priority != current.priority)
            || (self.queue_id.is_some() && self.queue_id != current.queue_id)
    }
}
