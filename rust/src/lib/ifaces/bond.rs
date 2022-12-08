// SPDX-License-Identifier: Apache-2.0

use std::convert::TryFrom;

use serde::{Deserialize, Serialize};

use crate::{
    deserializer::NumberAsString, BaseInterface, ErrorKind, Interface,
    InterfaceType, NmstateError,
};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
/// Bond interface. When serializing or deserializing, the [BaseInterface] will
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
    // Return None when desire state does not mention ports
    pub(crate) fn ports(&self) -> Option<Vec<&str>> {
        self.bond
            .as_ref()
            .and_then(|bond_conf| bond_conf.port.as_ref())
            .map(|ports| ports.as_slice().iter().map(|p| p.as_str()).collect())
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

    pub(crate) fn pre_edit_cleanup(
        &self,
        current: Option<&Interface>,
    ) -> Result<(), NmstateError> {
        self.validate_new_iface_with_no_mode(current)?;
        self.validate_mac_restricted_mode(current)?;
        let current_bond_conf =
            if let Some(Interface::Bond(cur_iface)) = current {
                cur_iface.bond.as_ref()
            } else {
                None
            };
        if let Some(bond_conf) = &self.bond {
            bond_conf.pre_edit_cleanup(current_bond_conf)?;
        }
        Ok(())
    }

    fn validate_new_iface_with_no_mode(
        &self,
        current: Option<&Interface>,
    ) -> Result<(), NmstateError> {
        if current.is_none() && self.mode().is_none() {
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
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[non_exhaustive]
#[serde(try_from = "NumberAsString")]
/// Bond mode
pub enum BondMode {
    #[serde(rename = "balance-rr")]
    /// Deserialize and serialize from/to `balance-rr`.
    /// You can use integer 0 for deserializing to this mode.
    RoundRobin,
    #[serde(rename = "active-backup")]
    /// Deserialize and serialize from/to `active-backup`.
    /// You can use integer 1 for deserializing to this mode.
    ActiveBackup,
    #[serde(rename = "balance-xor")]
    /// Deserialize and serialize from/to `balance-xor`.
    /// You can use integer 2 for deserializing to this mode.
    XOR,
    #[serde(rename = "broadcast")]
    /// Deserialize and serialize from/to `broadcast`.
    /// You can use integer 3 for deserializing to this mode.
    Broadcast,
    #[serde(rename = "802.3ad")]
    /// Deserialize and serialize from/to `802.3ad`.
    /// You can use integer 4 for deserializing to this mode.
    LACP,
    #[serde(rename = "balance-tlb")]
    /// Deserialize and serialize from/to `balance-tlb`.
    /// You can use integer 5 for deserializing to this mode.
    TLB,
    /// Deserialize and serialize from/to `balance-alb`.
    /// You can use integer 6 for deserializing to this mode.
    #[serde(rename = "balance-alb")]
    ALB,
    #[serde(rename = "unknown")]
    Unknown,
}

impl TryFrom<NumberAsString> for BondMode {
    type Error = NmstateError;
    fn try_from(s: NumberAsString) -> Result<Self, NmstateError> {
        match s.as_str() {
            "0" | "balance-rr" => Ok(Self::RoundRobin),
            "1" | "active-backup" => Ok(Self::ActiveBackup),
            "2" | "balance-xor" => Ok(Self::XOR),
            "3" | "broadcast" => Ok(Self::Broadcast),
            "4" | "802.3ad" => Ok(Self::LACP),
            "5" | "balance-tlb" => Ok(Self::TLB),
            "6" | "balance-alb" => Ok(Self::ALB),
            v => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!("Invalid bond mode {v}"),
            )),
        }
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
}

impl BondConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn pre_edit_cleanup(
        &self,
        current: Option<&Self>,
    ) -> Result<(), NmstateError> {
        let mode = match self.mode.or_else(|| current.and_then(|c| c.mode)) {
            Some(m) => m,
            None => {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Bond mode not defined in desire or current".to_string(),
                ));
            }
        };
        if let Some(opts) = &self.options {
            opts.pre_edit_cleanup(
                current.and_then(|c| c.options.as_ref()),
                mode,
            )?;
        }
        Ok(())
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case")]
#[serde(try_from = "NumberAsString")]
/// Specifies the 802.3ad aggregation selection logic to use.
pub enum BondAdSelect {
    /// Deserialize and serialize from/to `stable`.
    Stable,
    /// Deserialize and serialize from/to `bandwidth`.
    Bandwidth,
    /// Deserialize and serialize from/to `count`.
    Count,
}

impl TryFrom<NumberAsString> for BondAdSelect {
    type Error = NmstateError;
    fn try_from(s: NumberAsString) -> Result<Self, NmstateError> {
        match s.as_str() {
            "0" | "stable" => Ok(Self::Stable),
            "1" | "bandwidth" => Ok(Self::Bandwidth),
            "2" | "count" => Ok(Self::Count),
            s => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Invalid bond ad_select value: {s}, should be \
                    0, stable, 1, bandwidth, 2, or count"
                ),
            )),
        }
    }
}

impl From<BondAdSelect> for u8 {
    fn from(v: BondAdSelect) -> u8 {
        match v {
            BondAdSelect::Stable => 0,
            BondAdSelect::Bandwidth => 1,
            BondAdSelect::Count => 2,
        }
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
#[serde(rename_all = "kebab-case", try_from = "NumberAsString")]
#[non_exhaustive]
/// Option specifying the rate in which we'll ask our link partner to transmit
/// LACPDU packets in 802.3ad mode
pub enum BondLacpRate {
    /// Request partner to transmit LACPDUs every 30 seconds.
    /// Serialize to `slow`.
    /// Deserialize from 0 or `slow`.
    Slow,
    /// Request partner to transmit LACPDUs every 1 second
    /// Serialize to `fast`.
    /// Deserialize from 1 or `fast`.
    Fast,
}

impl TryFrom<NumberAsString> for BondLacpRate {
    type Error = NmstateError;
    fn try_from(s: NumberAsString) -> Result<Self, NmstateError> {
        match s.as_str() {
            "0" | "slow" => Ok(Self::Slow),
            "1" | "fast" => Ok(Self::Fast),
            v => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Invalid bond lacp-rate {v}, should be \
                    0, slow, 1 or fast"
                ),
            )),
        }
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
#[serde(rename_all = "kebab-case", try_from = "NumberAsString")]
#[non_exhaustive]
/// Equal to kernel `all_slaves_active` option.
/// Specifies that duplicate frames (received on inactive ports) should be
/// dropped (0) or delivered (1).
pub enum BondAllPortsActive {
    /// Drop the duplicate frames
    /// Serialize to `dropped`.
    /// Deserialize from 0 or `dropped`.
    Dropped,
    /// Deliver the duplicate frames
    /// Serialize to `delivered`.
    /// Deserialize from 1 or `delivered`.
    Delivered,
}

impl TryFrom<NumberAsString> for BondAllPortsActive {
    type Error = NmstateError;
    fn try_from(s: NumberAsString) -> Result<Self, NmstateError> {
        match s.as_str() {
            "0" | "dropped" => Ok(Self::Dropped),
            "1" | "delivered" => Ok(Self::Delivered),
            v => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Invalid all_slaves_active value: {v}, should be \
                    0, dropped, 1 or delivered"
                ),
            )),
        }
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

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone)]
#[serde(rename_all = "kebab-case", try_from = "NumberAsString")]
#[non_exhaustive]
/// The `arp_all_targets` kernel bond option: Specifies the quantity of
/// arp_ip_targets that must be reachable in order for the ARP monitor to
/// consider a port as being up. This option affects only active-backup mode
/// for ports with arp_validation enabled.
pub enum BondArpAllTargets {
    /// consider the port up only when any of the `arp_ip_targets` is reachable
    Any,
    /// consider the port up only when all of the `arp_ip_targets` are
    /// reachable
    All,
}

impl TryFrom<NumberAsString> for BondArpAllTargets {
    type Error = NmstateError;
    fn try_from(s: NumberAsString) -> Result<Self, NmstateError> {
        match s.as_str() {
            "0" | "any" => Ok(Self::Any),
            "1" | "all" => Ok(Self::All),
            v => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Invalid arp_all_targets value {v}, should be \
                    0, any, 1 or all"
                ),
            )),
        }
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

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone)]
#[serde(rename_all = "snake_case", try_from = "NumberAsString")]
#[non_exhaustive]
/// The `arp_validate` kernel bond option: Specifies whether or not ARP probes
/// and replies should be validated in any mode that supports arp monitoring, or
/// whether non-ARP traffic should be filtered (disregarded) for link monitoring
/// purposes.
pub enum BondArpValidate {
    /// No validation or filtering is performed.
    /// Serialize to `none`.
    /// Deserialize from 0 or `none`.
    None,
    /// Validation is performed only for the active port.
    /// Serialize to `active`.
    /// Deserialize from 1 or `active`.
    Active,
    /// Validation is performed only for backup ports.
    /// Serialize to `backup`.
    /// Deserialize from 2 or `backup`.
    Backup,
    /// Validation is performed for all ports.
    /// Serialize to `all`.
    /// Deserialize from 3 or `all`.
    All,
    /// Filtering is applied to all ports. No validation is performed.
    /// Serialize to `filter`.
    /// Deserialize from 4 or `filter`.
    Filter,
    /// Filtering is applied to all ports, validation is performed only for
    /// the active port.
    /// Serialize to `filter_active`.
    /// Deserialize from 5 or `filter-active`.
    FilterActive,
    /// Filtering is applied to all ports, validation is performed only for
    /// backup port.
    /// Serialize to `filter_backup`.
    /// Deserialize from 6 or `filter_backup`.
    FilterBackup,
}

impl TryFrom<NumberAsString> for BondArpValidate {
    type Error = NmstateError;
    fn try_from(s: NumberAsString) -> Result<Self, NmstateError> {
        match s.as_str() {
            "0" | "none" => Ok(Self::None),
            "1" | "active" => Ok(Self::Active),
            "2" | "backup" => Ok(Self::Backup),
            "3" | "all" => Ok(Self::All),
            "4" | "filter" => Ok(Self::Filter),
            "5" | "filter_active" => Ok(Self::FilterActive),
            "6" | "filter_backup" => Ok(Self::FilterBackup),
            v => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Invalid arp_validate value {v}, should be \
                    0, none, 1, active, 2, backup, 3, all, 4, filter, 5, \
                    filter_active, 6 or filter_backup"
                ),
            )),
        }
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

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[serde(rename_all = "kebab-case", try_from = "NumberAsString")]
#[non_exhaustive]
/// The `fail_over_mac` kernel bond option: Specifies whether active-backup mode
/// should set all ports to the same MAC address at port attachment (the
/// traditional behavior), or, when enabled, perform special handling of the
/// bond's MAC address in accordance with the selected policy.
pub enum BondFailOverMac {
    /// This setting disables fail_over_mac, and causes bonding to set all
    /// ports of an active-backup bond to the same MAC address at attachment
    /// time.
    /// Serialize to `none`.
    /// Deserialize from 0 or `none`.
    None,
    /// The "active" fail_over_mac policy indicates that the MAC address of the
    /// bond should always be the MAC address of the currently active port.
    /// The MAC address of the ports is not changed; instead, the MAC address
    /// of the bond changes during a failover.
    /// Serialize to `active`.
    /// Deserialize from 1 or `active`.
    Active,
    /// The "follow" fail_over_mac policy causes the MAC address of the bond to
    /// be selected normally (normally the MAC address of the first port added
    /// to the bond). However, the second and subsequent ports are not set to
    /// this MAC address while they are in a backup role; a port is programmed
    /// with the bond's MAC address at failover time (and the formerly active
    /// port receives the newly active port's MAC address).
    /// Serialize to `follow`.
    /// Deserialize from 2 or `follow`.
    Follow,
}

impl TryFrom<NumberAsString> for BondFailOverMac {
    type Error = NmstateError;
    fn try_from(s: NumberAsString) -> Result<Self, NmstateError> {
        match s.as_str() {
            "0" | "none" => Ok(Self::None),
            "1" | "active" => Ok(Self::Active),
            "2" | "follow" => Ok(Self::Follow),
            v => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Invalid fail_over_mac value: {v}, should be \
                    0, none, 1, active, 2 or follow"
                ),
            )),
        }
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

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone)]
#[serde(rename_all = "kebab-case", try_from = "NumberAsString")]
#[non_exhaustive]
/// The `primary_reselect` kernel bond option: Specifies the reselection policy
/// for the primary port. This affects how the primary port is chosen to
/// become the active port when failure of the active port or recovery of the
/// primary port occurs. This option is designed to prevent flip-flopping
/// between the primary port and other ports.
pub enum BondPrimaryReselect {
    ///The primary port becomes the active port whenever it comes back up.
    /// Serialize to `always`.
    /// Deserialize from 0 or `always`.
    Always,
    /// The primary port becomes the active port when it comes back up, if the
    /// speed and duplex of the primary port is better than the speed and
    /// duplex of the current active port.
    /// Serialize to `better`.
    /// Deserialize from 1 or `better`.
    Better,
    /// The primary port becomes the active port only if the current active
    /// port fails and the primary port is up.
    /// Serialize to `failure`.
    /// Deserialize from 2 or `failure`.
    Failure,
}

impl TryFrom<NumberAsString> for BondPrimaryReselect {
    type Error = NmstateError;
    fn try_from(s: NumberAsString) -> Result<Self, NmstateError> {
        match s.as_str() {
            "0" | "always" => Ok(Self::Always),
            "1" | "better" => Ok(Self::Better),
            "2" | "failure" => Ok(Self::Failure),
            v => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Invalid primary_reselect vlaue {v}, should be \
                    0, always, 1, better, 2 or failure"
                ),
            )),
        }
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

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[serde(try_from = "NumberAsString")]
#[non_exhaustive]
/// The `xmit_hash_policy` kernel bond option: Selects the transmit hash policy
/// to use for port selection in balance-xor, 802.3ad, and tlb modes.
pub enum BondXmitHashPolicy {
    #[serde(rename = "layer2")]
    /// Serialize to `layer2`.
    /// Deserialize from 0 or `layer2`.
    Layer2,
    #[serde(rename = "layer3+4")]
    /// Serialize to `layer3+4`.
    /// Deserialize from 1 or `layer3+4`.
    Layer34,
    #[serde(rename = "layer2+3")]
    /// Serialize to `layer2+3`.
    /// Deserialize from 2 or `layer2+3`.
    Layer23,
    #[serde(rename = "encap2+3")]
    /// Serialize to `encap2+3`.
    /// Deserialize from 3 or `encap2+3`.
    Encap23,
    #[serde(rename = "encap3+4")]
    /// Serialize to `encap3+4`.
    /// Deserialize from 4 or `encap3+4`.
    Encap34,
    #[serde(rename = "vlan+srcmac")]
    /// Serialize to `vlan+srcmac`.
    /// Deserialize from 5 or `vlan+srcmac`.
    VlanSrcMac,
}

impl TryFrom<NumberAsString> for BondXmitHashPolicy {
    type Error = NmstateError;
    fn try_from(s: NumberAsString) -> Result<Self, NmstateError> {
        match s.as_str() {
            "0" | "layer2" => Ok(Self::Layer2),
            "1" | "layer3+4" => Ok(Self::Layer34),
            "2" | "layer2+3" => Ok(Self::Layer23),
            "3" | "encap2+3" => Ok(Self::Encap23),
            "4" | "encap3+4" => Ok(Self::Encap34),
            "5" | "vlan+srcmac" => Ok(Self::VlanSrcMac),
            v => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Invalid xmit_hash_policy value {v}, should be \
                    0, layer2, 1, layer34, 2, layer23, 3, encap2+3, 4, \
                    encap3+4, 5, vlan+srcmac"
                ),
            )),
        }
    }
}

impl BondXmitHashPolicy {
    pub fn to_u8(&self) -> u8 {
        match self {
            Self::Layer2 => 0,
            Self::Layer34 => 1,
            Self::Layer23 => 2,
            Self::Encap23 => 3,
            Self::Encap34 => 4,
            Self::VlanSrcMac => 5,
        }
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
}

impl BondOptions {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn pre_edit_cleanup(
        &self,
        current: Option<&Self>,
        mode: BondMode,
    ) -> Result<(), NmstateError> {
        self.validate_ad_actor_system_mac_address()?;
        self.validate_miimon_and_arp_interval()?;
        self.validate_balance_slb(current, mode)?;
        Ok(())
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
