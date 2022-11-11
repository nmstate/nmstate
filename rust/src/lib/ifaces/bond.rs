use std::convert::TryFrom;

use serde::{Deserialize, Serialize};

use crate::{
    deserializer::NumberAsString, BaseInterface, ErrorKind, Interface,
    InterfaceType, NmstateError,
};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct BondInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "link-aggregation"
    )]
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
        if let Some(bond_conf) = &self.bond {
            bond_conf.pre_edit_cleanup()?;
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
pub enum BondMode {
    #[serde(rename = "balance-rr")]
    RoundRobin,
    #[serde(rename = "active-backup")]
    ActiveBackup,
    #[serde(rename = "balance-xor")]
    XOR,
    #[serde(rename = "broadcast")]
    Broadcast,
    #[serde(rename = "802.3ad")]
    LACP,
    #[serde(rename = "balance-tlb")]
    TLB,
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
    pub mode: Option<BondMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<BondOptions>,
    #[serde(skip_serializing_if = "Option::is_none", alias = "ports")]
    pub port: Option<Vec<String>>,
}

impl BondConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn pre_edit_cleanup(&self) -> Result<(), NmstateError> {
        if let Some(opts) = &self.options {
            opts.pre_edit_cleanup()?;
        }
        Ok(())
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case")]
#[serde(try_from = "NumberAsString")]
pub enum BondAdSelect {
    Stable,
    Bandwidth,
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
                    "Invalid bond ad_select value: {}, should be \
                    0, stable, 1, bandwidth, 2, or count",
                    s
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
pub enum BondLacpRate {
    Slow,
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
                    "Invalid bond lacp-rate {}, should be \
                    0, slow, 1 or fast",
                    v
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
pub enum BondAllPortsActive {
    Dropped,
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
                    "Invalid all_slaves_active value: {}, should be \
                    0, dropped, 1 or delivered",
                    v
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
pub enum BondArpAllTargets {
    Any,
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
                    "Invalid arp_all_targets value {}, should be \
                    0, any, 1 or all",
                    v
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
#[serde(rename_all = "kebab-case", try_from = "NumberAsString")]
#[non_exhaustive]
pub enum BondArpValidate {
    None,
    Active,
    Backup,
    All,
    Filter,
    FilterActive,
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
                    "Invalid arp_validate value {}, should be \
                    0, none, 1, active, 2, backup, 3, all, 4, filter, 5, \
                    filter_active, 6 or filter_backup",
                    v
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
pub enum BondFailOverMac {
    None,
    Active,
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
                    "Invalid fail_over_mac value: {}, should be \
                    0, none, 1, active, 2 or follow",
                    v
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
pub enum BondPrimaryReselect {
    Always,
    Better,
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
                    "Invalid primary_reselect vlaue {}, should be \
                    0, always, 1, better, 2 or failure",
                    v
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

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone)]
#[serde(try_from = "NumberAsString")]
#[non_exhaustive]
pub enum BondXmitHashPolicy {
    #[serde(rename = "layer2")]
    Layer2,
    #[serde(rename = "layer3+4")]
    Layer34,
    #[serde(rename = "layer2+3")]
    Layer23,
    #[serde(rename = "encap2+3")]
    Encap23,
    #[serde(rename = "encap3+4")]
    Encap34,
    #[serde(rename = "vlan+srcmac")]
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
                    "Invalid xmit_hash_policy value {}, should be \
                    0, layer2, 1, layer34, 2, layer23, 3, encap2+3, 4, \
                    encap3+4, 5, vlan+srcmac",
                    v
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
    pub ad_actor_sys_prio: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ad_actor_system: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ad_select: Option<BondAdSelect>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u16_or_string"
    )]
    pub ad_user_port_key: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub all_slaves_active: Option<BondAllPortsActive>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arp_all_targets: Option<BondArpAllTargets>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub arp_interval: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arp_ip_target: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arp_validate: Option<BondArpValidate>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub downdelay: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fail_over_mac: Option<BondFailOverMac>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lacp_rate: Option<BondLacpRate>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub lp_interval: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub miimon: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub min_links: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u8_or_string"
    )]
    pub num_grat_arp: Option<u8>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u8_or_string"
    )]
    pub num_unsol_na: Option<u8>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub packets_per_slave: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub primary: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub primary_reselect: Option<BondPrimaryReselect>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub resend_igmp: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub tlb_dynamic_lb: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub updelay: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub use_carrier: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub xmit_hash_policy: Option<BondXmitHashPolicy>,
}

impl BondOptions {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn pre_edit_cleanup(&self) -> Result<(), NmstateError> {
        self.validate_ad_actor_system_mac_address()?;
        self.validate_miimon_and_arp_interval()?;
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
}
