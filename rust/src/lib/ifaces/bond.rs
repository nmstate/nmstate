use crate::{BaseInterface, ErrorKind, InterfaceType, NmstateError};
use serde::{de::Error, Deserialize, Deserializer, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
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
    pub(crate) fn update_bond(&mut self, other: &BondInterface) {
        if let Some(bond_conf) = &mut self.bond {
            bond_conf.update(other.bond.as_ref());
        } else {
            self.bond = other.bond.clone();
        }
    }

    // Return None when desire state does not mention ports
    pub(crate) fn ports(&self) -> Option<Vec<&str>> {
        self.bond
            .as_ref()
            .and_then(|bond_conf| bond_conf.port.as_ref())
            .map(|ports| ports.as_slice().iter().map(|p| p.as_str()).collect())
    }

    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.drop_empty_arp_ip_target();
        self.sort_ports();
    }

    pub fn new() -> Self {
        Self::default()
    }

    fn sort_ports(&mut self) {
        if let Some(ref mut bond_conf) = self.bond {
            if let Some(ref mut port_conf) = &mut bond_conf.port {
                port_conf.sort_unstable_by_key(|p| p.clone())
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

    pub(crate) fn validate(&self) -> Result<(), NmstateError> {
        self.base.validate()?;
        if let Some(bond_conf) = &self.bond {
            bond_conf.validate(&self.base)?;
        }
        Ok(())
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
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
#[non_exhaustive]
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
    Unknown,
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

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct BondConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mode: Option<BondMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<BondOptions>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub port: Option<Vec<String>>,
}

impl BondConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn validate(
        &self,
        base: &BaseInterface,
    ) -> Result<(), NmstateError> {
        if let Some(opts) = &self.options {
            if let Some(mode) = &self.mode {
                opts.validate(mode, base)?;
            } else {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Bond mode is mandatory".to_string(),
                ));
            }
        }

        if self.mode.is_none() {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                "Bond mode is mandatory".to_string(),
            ));
        }

        Ok(())
    }

    pub(crate) fn update(&mut self, other: Option<&BondConfig>) {
        if let Some(other) = other {
            self.mode = other.mode.clone();
            self.options = other.options.clone();
            self.port = other.port.clone();
        }
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum BondAdSelect {
    #[serde(alias = "0")]
    Stable,
    #[serde(alias = "1")]
    Bandwidth,
    #[serde(alias = "2")]
    Count,
}

impl BondAdSelect {
    pub fn to_u8(&self) -> u8 {
        match self {
            Self::Stable => 0,
            Self::Bandwidth => 1,
            Self::Count => 2,
        }
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum BondLacpRate {
    #[serde(alias = "0")]
    Slow,
    #[serde(alias = "1")]
    Fast,
}

impl BondLacpRate {
    pub fn to_u8(&self) -> u8 {
        match self {
            Self::Slow => 0,
            Self::Fast => 1,
        }
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum BondAllPortsActive {
    #[serde(alias = "0")]
    Dropped,
    #[serde(alias = "1")]
    Delivered,
}

impl BondAllPortsActive {
    pub fn to_u8(&self) -> u8 {
        match self {
            Self::Dropped => 0,
            Self::Delivered => 1,
        }
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum BondArpAllTargets {
    #[serde(alias = "0")]
    Any,
    #[serde(alias = "1")]
    All,
}

impl BondArpAllTargets {
    pub fn to_u32(&self) -> u32 {
        match self {
            Self::Any => 0,
            Self::All => 1,
        }
    }
}

const BOND_STATE_ACTIVE: u8 = 0;
const BOND_STATE_BACKUP: u8 = 1;

const BOND_ARP_VALIDATE_NONE: u32 = 0;
const BOND_ARP_VALIDATE_ACTIVE: u32 = 1 << BOND_STATE_ACTIVE as u32;
const BOND_ARP_VALIDATE_BACKUP: u32 = 1 << BOND_STATE_BACKUP as u32;
const BOND_ARP_VALIDATE_ALL: u32 =
    BOND_ARP_VALIDATE_ACTIVE | BOND_ARP_VALIDATE_BACKUP;
const BOND_ARP_FILTER: u32 = BOND_ARP_VALIDATE_ALL + 1;
const BOND_ARP_FILTER_ACTIVE: u32 = BOND_ARP_VALIDATE_ACTIVE | BOND_ARP_FILTER;
const BOND_ARP_FILTER_BACKUP: u32 = BOND_ARP_VALIDATE_BACKUP | BOND_ARP_FILTER;

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum BondArpValidate {
    None,
    Active,
    Backup,
    All,
    Filter,
    #[serde(rename = "filter_active")]
    FilterActive,
    #[serde(rename = "filter_backup")]
    FilterBackup,
}

impl BondArpValidate {
    pub fn to_u32(&self) -> u32 {
        match self {
            Self::None => BOND_ARP_VALIDATE_NONE,
            Self::Active => BOND_ARP_VALIDATE_ACTIVE,
            Self::Backup => BOND_ARP_VALIDATE_BACKUP,
            Self::All => BOND_ARP_VALIDATE_ALL,
            Self::Filter => BOND_ARP_FILTER,
            Self::FilterActive => BOND_ARP_FILTER_ACTIVE,
            Self::FilterBackup => BOND_ARP_FILTER_BACKUP,
        }
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum BondFailOverMac {
    #[serde(alias = "0")]
    None,
    #[serde(alias = "1")]
    Active,
    #[serde(alias = "2")]
    Follow,
}

impl BondFailOverMac {
    pub fn to_u8(&self) -> u8 {
        match self {
            Self::None => 0,
            Self::Active => 1,
            Self::Follow => 2,
        }
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum BondPrimaryReselect {
    #[serde(alias = "0")]
    Always,
    #[serde(alias = "1")]
    Better,
    #[serde(alias = "2")]
    Failure,
}

impl BondPrimaryReselect {
    pub fn to_u8(&self) -> u8 {
        match self {
            Self::Always => 0,
            Self::Better => 1,
            Self::Failure => 2,
        }
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
#[non_exhaustive]
pub enum BondXmitHashPolicy {
    #[serde(rename = "layer2")]
    #[serde(alias = "0")]
    Layer2,
    #[serde(rename = "layer3+4")]
    #[serde(alias = "1")]
    Layer34,
    #[serde(rename = "layer2+3")]
    #[serde(alias = "2")]
    Layer23,
    #[serde(rename = "encap2+3")]
    #[serde(alias = "3")]
    Encap23,
    #[serde(rename = "encap3+4")]
    #[serde(alias = "4")]
    Encap34,
    #[serde(rename = "vlan+srcmac")]
    #[serde(alias = "5")]
    VlanSrcMac,
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

#[derive(Debug, Serialize, Deserialize, Default, Clone, PartialEq)]
#[non_exhaustive]
pub struct BondOptions {
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u16",
        default
    )]
    pub ad_actor_sys_prio: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ad_actor_system: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ad_select: Option<BondAdSelect>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u16",
        default
    )]
    pub ad_user_port_key: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub all_slaves_active: Option<BondAllPortsActive>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arp_all_targets: Option<BondArpAllTargets>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u32",
        default
    )]
    pub arp_interval: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arp_ip_target: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arp_validate: Option<BondArpValidate>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u32",
        default
    )]
    pub downdelay: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fail_over_mac: Option<BondFailOverMac>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lacp_rate: Option<BondLacpRate>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u32",
        default
    )]
    pub lp_interval: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u32",
        default
    )]
    pub miimon: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u32",
        default
    )]
    pub min_links: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u8",
        default
    )]
    pub num_grat_arp: Option<u8>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u8",
        default
    )]
    pub num_unsol_na: Option<u8>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u32",
        default
    )]
    pub packets_per_slave: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub primary: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub primary_reselect: Option<BondPrimaryReselect>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u32",
        default
    )]
    pub resend_igmp: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tlb_dynamic_lb: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        deserialize_with = "json_to_u32",
        default
    )]
    pub updelay: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub use_carrier: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub xmit_hash_policy: Option<BondXmitHashPolicy>,
}

fn json_to_u32<'de, D>(deserializer: D) -> Result<Option<u32>, D::Error>
where
    D: Deserializer<'de>,
{
    let json_value: serde_json::Value = Deserialize::deserialize(deserializer)?;
    let u32_value: u32 = match json_value.as_u64() {
        None => {
            if let Some(str_value) = json_value.as_str() {
                if str_value.chars().all(char::is_numeric) {
                    str_value.parse::<u32>().map_err(D::Error::custom)?
                } else {
                    return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!("Property value: {} is not valid, only numeric values are allowed.", str_value)))
                    .map_err(D::Error::custom);
                }
            } else {
                return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!("Property value: {} is not valid, only numeric values are allowed.", json_value)))
                .map_err(D::Error::custom);
            }
        }
        Some(u64_value) => u64_value as u32,
    };

    Ok(Some(u32_value))
}

fn json_to_u16<'de, D>(deserializer: D) -> Result<Option<u16>, D::Error>
where
    D: Deserializer<'de>,
{
    if let Some(u32_value) = json_to_u32(deserializer)? {
        Ok(Some(u32_value as u16))
    } else {
        Ok(None)
    }
}

fn json_to_u8<'de, D>(deserializer: D) -> Result<Option<u8>, D::Error>
where
    D: Deserializer<'de>,
{
    if let Some(u32_value) = json_to_u32(deserializer)? {
        Ok(Some(u32_value as u8))
    } else {
        Ok(None)
    }
}

impl BondOptions {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn validate(
        &self,
        mode: &BondMode,
        base: &BaseInterface,
    ) -> Result<(), NmstateError> {
        self.fix_mac_restricted_mode(mode, base)?;
        self.validate_ad_actor_system_mac_address()?;
        self.validate_miimon_and_arp_interval()?;
        Ok(())
    }

    fn fix_mac_restricted_mode(
        &self,
        mode: &BondMode,
        base: &BaseInterface,
    ) -> Result<(), NmstateError> {
        if let Some(fail_over_mac) = &self.fail_over_mac {
            if *mode == BondMode::ActiveBackup
                && *fail_over_mac == BondFailOverMac::Active
                && base.mac_address.is_some()
            {
                return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                            "MAC address cannot be specified in bond interface along with fail_over_mac active on active backup mode".to_string()
                    ));
            }
        }
        Ok(())
    }

    fn validate_ad_actor_system_mac_address(&self) -> Result<(), NmstateError> {
        if let Some(ad_actor_system) = &self.ad_actor_system {
            if ad_actor_system.to_uppercase().starts_with("01:00:5E") {
                return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                            "The ad_actor_system bond option cannot be an IANA multicast address(prefix with 01:00:5E)".to_string()
                    ));
            }
        }
        Ok(())
    }

    fn validate_miimon_and_arp_interval(&self) -> Result<(), NmstateError> {
        if let Some(miimon) = &self.miimon {
            if let Some(arp_interval) = &self.arp_interval {
                if miimon > &0 && arp_interval > &0 {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                            "Bond miimon and arp interval are not compatible options.".to_string()
                    ));
                }
            }
        }
        Ok(())
    }
}
