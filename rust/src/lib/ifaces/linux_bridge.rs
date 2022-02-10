use std::collections::HashMap;

use log::{error, warn};
use serde::{Deserialize, Serialize};

use crate::{BaseInterface, ErrorKind, InterfaceType, NmstateError};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
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
    pub(crate) const INTEGER_ROUNDED_OPTIONS: [&'static str; 5] = [
        "interface.bridge.options.multicast-last-member-interval",
        "interface.bridge.options.multicast-membership-interval",
        "interface.bridge.options.multicast-querier-interval",
        "interface.bridge.options.multicast-query-response-interval",
        "interface.bridge.options.multicast-startup-query-interval",
    ];

    pub(crate) fn update_bridge(&mut self, other: &LinuxBridgeInterface) {
        if let Some(br_conf) = &mut self.bridge {
            br_conf.update(other.bridge.as_ref());
        } else {
            self.bridge = other.bridge.clone();
        }
    }

    // Return None when desire state does not mentioned ports.
    pub(crate) fn ports(&self) -> Option<Vec<&str>> {
        self.bridge
            .as_ref()
            .and_then(|br_conf| br_conf.port.as_ref())
            .map(|ports| {
                ports.as_slice().iter().map(|p| p.name.as_str()).collect()
            })
    }

    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.sort_ports();
        self.use_upper_case_of_mac_address();
        self.flatten_port_vlan_ranges();
        self.sort_port_vlans();
        self.treat_none_vlan_as_empty_dict();
    }

    pub fn new() -> Self {
        Self::default()
    }

    fn sort_ports(&mut self) {
        if let Some(ref mut br_conf) = self.bridge {
            if let Some(ref mut port_confs) = &mut br_conf.port {
                port_confs.sort_unstable_by_key(|p| p.name.clone())
            }
        }
    }

    fn use_upper_case_of_mac_address(&mut self) {
        if let Some(address) = self
            .bridge
            .as_mut()
            .and_then(|br_conf| br_conf.options.as_mut())
            .and_then(|br_opts| br_opts.group_addr.as_mut())
        {
            address.make_ascii_uppercase()
        }
    }

    fn flatten_port_vlan_ranges(&mut self) {
        if let Some(port_confs) = self
            .bridge
            .as_mut()
            .and_then(|br_conf| br_conf.port.as_mut())
        {
            for port_conf in port_confs {
                port_conf
                    .vlan
                    .as_mut()
                    .map(LinuxBridgePortVlanConfig::flatten_vlan_ranges);
            }
        }
    }

    fn sort_port_vlans(&mut self) {
        if let Some(port_confs) = self
            .bridge
            .as_mut()
            .and_then(|br_conf| br_conf.port.as_mut())
        {
            for port_conf in port_confs {
                port_conf
                    .vlan
                    .as_mut()
                    .map(LinuxBridgePortVlanConfig::sort_trunk_tags);
            }
        }
    }

    fn treat_none_vlan_as_empty_dict(&mut self) {
        if let Some(port_confs) = self
            .bridge
            .as_mut()
            .and_then(|br_conf| br_conf.port.as_mut())
        {
            for port_conf in port_confs {
                if port_conf.vlan.is_none() {
                    port_conf.vlan = Some(LinuxBridgePortVlanConfig::new());
                }
            }
        }
    }

    pub(crate) fn remove_port(&mut self, port_name: &str) {
        if let Some(index) = self.bridge.as_ref().and_then(|br_conf| {
            br_conf.port.as_ref().and_then(|port_confs| {
                port_confs
                    .iter()
                    .position(|port_conf| port_conf.name == port_name)
            })
        }) {
            self.bridge
                .as_mut()
                .and_then(|br_conf| br_conf.port.as_mut())
                .map(|port_confs| port_confs.remove(index));
        }
    }

    pub(crate) fn validate(&self) -> Result<(), NmstateError> {
        self.base.validate()?;
        self.bridge
            .as_ref()
            .map(LinuxBridgeConfig::validate)
            .transpose()?;
        Ok(())
    }

    pub(crate) fn get_port_conf(
        &self,
        port_name: &str,
    ) -> Option<&LinuxBridgePortConfig> {
        self.bridge
            .as_ref()
            .and_then(|br_conf| br_conf.port.as_ref())
            .and_then(|port_confs| {
                port_confs
                    .iter()
                    .find(|port_conf| port_conf.name == port_name)
            })
    }

    pub(crate) fn vlan_filtering_is_enabled(&self) -> bool {
        self.bridge
            .as_ref()
            .and_then(|br_conf| br_conf.port.as_ref())
            .map(|port_confs| {
                port_confs.iter().any(|port_conf| port_conf.vlan.is_some())
            })
            .unwrap_or(false)
    }

    // Port name list change is not this function's responsibility, top level
    // code will take care of it.
    // This function only find out those port which has changed vlan or stp
    // configuration.
    pub(crate) fn get_config_changed_ports(&self, current: &Self) -> Vec<&str> {
        let mut ret: Vec<&str> = Vec::new();
        let mut des_ports_index: HashMap<&str, &LinuxBridgePortConfig> =
            HashMap::new();
        let mut cur_ports_index: HashMap<&str, &LinuxBridgePortConfig> =
            HashMap::new();
        if let Some(port_confs) = self
            .bridge
            .as_ref()
            .and_then(|br_conf| br_conf.port.as_ref())
        {
            for port_conf in port_confs {
                des_ports_index.insert(port_conf.name.as_str(), port_conf);
            }
        }

        if let Some(port_confs) = current
            .bridge
            .as_ref()
            .and_then(|br_conf| br_conf.port.as_ref())
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

    // With 250 kernel HZ(Ubuntu kernel) and 100 user HZ, some linux bridge
    // kernel option value will be rounded up with 1 difference which lead to
    // verification error.
    pub(crate) fn is_interger_rounded_up(prop_full_name: &str) -> bool {
        for allowed_prop_name in &Self::INTEGER_ROUNDED_OPTIONS {
            if prop_full_name.ends_with(allowed_prop_name) {
                return true;
            }
        }
        false
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct LinuxBridgeConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<LinuxBridgeOptions>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub port: Option<Vec<LinuxBridgePortConfig>>,
}

impl LinuxBridgeConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn validate(&self) -> Result<(), NmstateError> {
        self.options
            .as_ref()
            .map(LinuxBridgeOptions::validate)
            .transpose()?;
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct LinuxBridgePortConfig {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stp_hairpin_mode: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stp_path_cost: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stp_priority: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vlan: Option<LinuxBridgePortVlanConfig>,
}

impl LinuxBridgePortConfig {
    pub fn new() -> Self {
        Self::default()
    }

    fn is_changed(&self, current: &Self) -> bool {
        (self.stp_hairpin_mode.is_some()
            && self.stp_hairpin_mode != current.stp_hairpin_mode)
            || (self.stp_path_cost.is_some()
                && self.stp_path_cost != current.stp_path_cost)
            || (self.stp_priority.is_some()
                && self.stp_priority != current.stp_priority)
            || match (self.vlan.as_ref(), current.vlan.as_ref()) {
                (Some(des_vlan_conf), Some(cur_vlan_conf)) => {
                    des_vlan_conf.is_changed(cur_vlan_conf)
                }
                (Some(_), None) => true,
                _ => false,
            }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct LinuxBridgeOptions {
    // `gc_timer` is runtime status, not allowing for changing
    #[serde(skip_serializing_if = "Option::is_none", skip_deserializing)]
    pub gc_timer: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub group_addr: Option<String>,
    // The group_forward_mask is the same with group_fwd_mask. The former is
    // used by NetworkManager, the later is used by sysfs. Nmstate support
    // both.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub group_forward_mask: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub group_fwd_mask: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hash_max: Option<u32>,
    // `hello_timer` is runtime status, not allowing for changing
    #[serde(skip_serializing_if = "Option::is_none", skip_deserializing)]
    pub hello_timer: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mac_ageing_time: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_last_member_count: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_last_member_interval: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_membership_interval: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_querier: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_querier_interval: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_query_interval: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_query_response_interval: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_query_use_ifaddr: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_router: Option<LinuxBridgeMulticastRouterType>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_snooping: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_startup_query_count: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multicast_startup_query_interval: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stp: Option<LinuxBridgeStpOptions>,
}

impl LinuxBridgeOptions {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn validate(&self) -> Result<(), NmstateError> {
        self.stp
            .as_ref()
            .map(LinuxBridgeStpOptions::validate)
            .transpose()?;
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct LinuxBridgeStpOptions {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enabled: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub forward_delay: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hello_time: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_age: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub priority: Option<u16>,
}

impl LinuxBridgeStpOptions {
    pub const HELLO_TIME_MAX: u8 = 10;
    pub const HELLO_TIME_MIN: u8 = 1;
    pub const MAX_AGE_MAX: u8 = 40;
    pub const MAX_AGE_MIN: u8 = 6;
    pub const FORWARD_DELAY_MAX: u8 = 30;
    pub const FORWARD_DELAY_MIN: u8 = 2;

    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn validate(&self) -> Result<(), NmstateError> {
        if let Some(hello_time) = self.hello_time {
            if !(Self::HELLO_TIME_MIN..=Self::HELLO_TIME_MAX)
                .contains(&hello_time)
            {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Desired STP hello time {} is not in the range \
                        of [{},{}]",
                        hello_time,
                        Self::HELLO_TIME_MIN,
                        Self::HELLO_TIME_MAX
                    ),
                );
                error!("{}", e);
                return Err(e);
            }
        }

        if let Some(max_age) = self.max_age {
            if !(Self::MAX_AGE_MIN..=Self::MAX_AGE_MAX).contains(&max_age) {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Desired STP max age {} is not in the range \
                        of [{},{}]",
                        max_age,
                        Self::MAX_AGE_MIN,
                        Self::MAX_AGE_MAX
                    ),
                );
                error!("{}", e);
                return Err(e);
            }
        }
        if let Some(forward_delay) = self.forward_delay {
            if !(Self::FORWARD_DELAY_MIN..=Self::FORWARD_DELAY_MAX)
                .contains(&forward_delay)
            {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Desired STP forward delay {} is not in the range \
                        of [{},{}]",
                        forward_delay,
                        Self::FORWARD_DELAY_MIN,
                        Self::FORWARD_DELAY_MAX
                    ),
                );
                error!("{}", e);
                return Err(e);
            }
        }
        Ok(())
    }
}

impl LinuxBridgeConfig {
    pub(crate) fn update(&mut self, other: Option<&LinuxBridgeConfig>) {
        if let Some(other) = other {
            self.options = other.options.clone();
            self.port = other.port.clone();
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum LinuxBridgeMulticastRouterType {
    Auto,
    Disabled,
    Enabled,
}

impl Default for LinuxBridgeMulticastRouterType {
    fn default() -> Self {
        Self::Auto
    }
}

impl std::fmt::Display for LinuxBridgeMulticastRouterType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Auto => "auto",
                Self::Disabled => "disabled",
                Self::Enabled => "enabled",
            }
        )
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct LinuxBridgePortVlanConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enable_native: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mode: Option<LinuxBridgePortVlanMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tag: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trunk_tags: Option<Vec<LinuxBridgePortTunkTag>>,
}

impl LinuxBridgePortVlanConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn flatten_vlan_ranges(&mut self) {
        if let Some(trunk_tags) = &self.trunk_tags {
            let mut new_trunk_tags = Vec::new();
            for trunk_tag in trunk_tags {
                match trunk_tag {
                    LinuxBridgePortTunkTag::Id(_) => {
                        new_trunk_tags.push(trunk_tag.clone())
                    }
                    LinuxBridgePortTunkTag::IdRange(range) => {
                        for i in range.min..range.max + 1 {
                            new_trunk_tags.push(LinuxBridgePortTunkTag::Id(i));
                        }
                    }
                };
            }
            self.trunk_tags = Some(new_trunk_tags);
        }
    }

    pub(crate) fn sort_trunk_tags(&mut self) {
        if let Some(trunk_tags) = self.trunk_tags.as_mut() {
            trunk_tags.sort_unstable_by(|tag_a, tag_b| match (tag_a, tag_b) {
                (
                    LinuxBridgePortTunkTag::Id(a),
                    LinuxBridgePortTunkTag::Id(b),
                ) => a.cmp(b),
                _ => {
                    warn!(
                        "Please call flatten_vlan_ranges() \
                            before sort_port_vlans()"
                    );
                    std::cmp::Ordering::Equal
                }
            })
        }
    }

    pub(crate) fn is_changed(&self, current: &Self) -> bool {
        (self.enable_native.is_some()
            && self.enable_native != current.enable_native)
            || (self.mode.is_some() && self.mode != current.mode)
            || (self.tag.is_some() && self.tag != current.tag)
            || (self.trunk_tags.is_some()
                && self.trunk_tags != current.trunk_tags)
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum LinuxBridgePortVlanMode {
    Trunk,
    Access,
}

impl Default for LinuxBridgePortVlanMode {
    fn default() -> Self {
        Self::Access
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum LinuxBridgePortTunkTag {
    Id(u16),
    IdRange(LinuxBridgePortVlanRange),
}

impl LinuxBridgePortTunkTag {
    pub fn get_vlan_tag_range(&self) -> (u16, u16) {
        match self {
            Self::Id(min) => (*min, *min),
            Self::IdRange(range) => (range.min, range.max),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[non_exhaustive]
pub struct LinuxBridgePortVlanRange {
    pub max: u16,
    pub min: u16,
}
