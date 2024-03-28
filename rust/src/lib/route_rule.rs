// SPDX-License-Identifier: Apache-2.0

use std::hash::{Hash, Hasher};

use serde::{Deserialize, Serialize};

use crate::{
    ip::{is_ipv6_addr, sanitize_ip_network, AddressFamily},
    ErrorKind, InterfaceIpAddr, InterfaceType, NmstateError,
};

const ROUTE_RULE_DEFAULT_PRIORIRY: i64 = 30000;

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
/// Routing rules
pub struct RouteRules {
    #[serde(skip_serializing_if = "Option::is_none")]
    /// When applying, `None` means preserve existing route rules.
    /// Nmstate is using partial editing for route rule, which means
    /// desired route rules only append to existing instead of overriding.
    /// To delete any route rule, please set [crate::RouteRuleEntry.state] to
    /// [RouteRuleState::Absent]. Any property set to None in absent route rule
    /// means wildcard. For example, this [crate::NetworkState] will delete all
    /// route rule looking up route table 500:
    /// ```yml
    /// ---
    /// route-rules:
    ///   config:
    ///     - state: absent
    ///       route-table: 500
    /// ```
    pub config: Option<Vec<RouteRuleEntry>>,
}

impl RouteRules {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn is_empty(&self) -> bool {
        self.config.is_none()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum RouteRuleState {
    /// Used for delete route rule
    Absent,
}

impl Default for RouteRuleState {
    fn default() -> Self {
        Self::Absent
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
pub struct RouteRuleEntry {
    /// Indicate the address family of the route rule.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub family: Option<AddressFamily>,
    /// Indicate this is normal route rule or absent route rule.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub state: Option<RouteRuleState>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Source prefix to match.
    /// Serialize and deserialize to/from `ip-from`.
    /// When setting to empty string in absent route rule, it will only delete
    /// route rule __without__ `ip-from`.
    pub ip_from: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Destination prefix to match.
    /// Serialize and deserialize to/from `ip-to`.
    /// When setting to empty string in absent route rule, it will only delete
    /// route rule __without__ `ip-to`.
    pub ip_to: Option<String>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_i64_or_string"
    )]
    /// Priority of this route rule.
    /// Bigger number means lower priority.
    pub priority: Option<i64>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "route-table",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// The routing table ID to lookup if the rule selector matches.
    /// Serialize and deserialize to/from `route-table`.
    pub table_id: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string",
        serialize_with = "crate::serializer::option_u32_as_hex"
    )]
    /// Select the fwmark value to match
    pub fwmark: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string",
        serialize_with = "crate::serializer::option_u32_as_hex"
    )]
    /// Select the fwmask value to match
    pub fwmask: Option<u32>,
    /// Actions for matching packages.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub action: Option<RouteRuleAction>,
    /// Incoming interface.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub iif: Option<String>,
    /// Prefix length of suppressor.
    /// Can deserialize from `suppress-prefix-length` or
    /// `suppress_prefixlength`.
    /// Serialize into `suppress-prefix-length`.
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "suppress_prefixlength"
    )]
    pub suppress_prefix_length: Option<u32>,
}

impl RouteRuleEntry {
    /// Let network backend choose the default priority.
    pub const USE_DEFAULT_PRIORITY: i64 = -1;
    /// Use main route table 254.
    pub const USE_DEFAULT_ROUTE_TABLE: u32 = 0;
    /// Default route table main(254).
    pub const DEFAULR_ROUTE_TABLE_ID: u32 = 254;

    pub fn new() -> Self {
        Self::default()
    }

    fn validate_ip_from_to(&self) -> Result<(), NmstateError> {
        if self.ip_from.is_none()
            && self.ip_to.is_none()
            && self.family.is_none()
        {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Neither ip-from, ip-to nor family is defined '{self}'"
                ),
            );
            log::error!("{}", e);
            return Err(e);
        } else if let Some(family) = self.family {
            if let Some(ip_from) = self.ip_from.as_ref() {
                if is_ipv6_addr(ip_from.as_str())
                    != matches!(family, AddressFamily::IPv6)
                {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "The ip-from format mismatches with the \
                            family set '{self}'"
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
            if let Some(ip_to) = self.ip_to.as_ref() {
                if is_ipv6_addr(ip_to.as_str())
                    != matches!(family, AddressFamily::IPv6)
                {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "The ip-to format mismatches with the family \
                            set {self}"
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
        }
        Ok(())
    }

    fn validate_fwmark_and_fwmask(&self) -> Result<(), NmstateError> {
        if self.fwmark.is_none() && self.fwmask.is_some() {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "fwmask is present but fwmark is \
                    not defined or is zero {self:?}"
                ),
            );
            log::error!("{}", e);
            return Err(e);
        }
        Ok(())
    }

    pub(crate) fn is_absent(&self) -> bool {
        matches!(self.state, Some(RouteRuleState::Absent))
    }

    pub(crate) fn is_ipv6(&self) -> bool {
        self.family.as_ref() == Some(&AddressFamily::IPv6)
            || self.ip_from.as_ref().map(|i| is_ipv6_addr(i.as_str()))
                == Some(true)
            || self.ip_to.as_ref().map(|i| is_ipv6_addr(i.as_str()))
                == Some(true)
    }

    pub(crate) fn is_match(&self, other: &Self) -> bool {
        if let Some(ip_from) = self.ip_from.as_deref() {
            if !ip_from.is_empty() {
                let ip_from = if !ip_from.contains('/') {
                    match InterfaceIpAddr::try_from(ip_from) {
                        Ok(i) => i.to_string(),
                        Err(e) => {
                            log::error!("{}", e);
                            return false;
                        }
                    }
                } else {
                    ip_from.to_string()
                };
                if other.ip_from != Some(ip_from) {
                    return false;
                }
            } else if other.ip_from.as_deref().map(|s| s.is_empty())
                == Some(false)
            {
                // Use desire 'ip_from: ""' means it should only match empty
                // ip_from
                return false;
            }
        }
        if let Some(ip_to) = self.ip_to.as_deref() {
            if !ip_to.is_empty() {
                let ip_to = if !ip_to.contains('/') {
                    match InterfaceIpAddr::try_from(ip_to) {
                        Ok(ref i) => i.to_string(),
                        Err(e) => {
                            log::error!("{}", e);
                            return false;
                        }
                    }
                } else {
                    ip_to.to_string()
                };
                if other.ip_to != Some(ip_to) {
                    return false;
                }
            } else if other.ip_to.as_deref().map(|s| s.is_empty())
                == Some(false)
            {
                // Use desire 'ip_to: ""' means it should only match empty
                // ip_to
                return false;
            }
        }
        if self.family.is_some()
            && other.family.is_some()
            && self.family != other.family
        {
            return false;
        }

        if self.priority.is_some()
            && self.priority != Some(RouteRuleEntry::USE_DEFAULT_PRIORITY)
            && self.priority != other.priority
            && !(self.priority == Some(0) && other.priority.is_none())
        {
            return false;
        }
        if self.table_id.is_some()
            && self.table_id != Some(RouteRuleEntry::USE_DEFAULT_ROUTE_TABLE)
            && self.table_id != other.table_id
        {
            return false;
        }
        if self.fwmark.is_some()
            && self.fwmark.unwrap_or(0) != other.fwmark.unwrap_or(0)
        {
            return false;
        }
        if self.fwmask.is_some()
            && self.fwmask.unwrap_or(0) != other.fwmask.unwrap_or(0)
        {
            return false;
        }
        if self.iif.is_some() && self.iif != other.iif {
            return false;
        }
        if self.action.is_some() && self.action != other.action {
            return false;
        }
        if self.suppress_prefix_length.is_some()
            && self.suppress_prefix_length != other.suppress_prefix_length
        {
            return false;
        }
        true
    }

    // Return tuple of (no_absent, is_ipv4, table_id, ip_from,
    // ip_to, priority, fwmark, fwmask, action, suppress_prefix_length)
    fn sort_key(
        &self,
    ) -> (bool, bool, u32, &str, &str, i64, u32, u32, u8, u32) {
        (
            !matches!(self.state, Some(RouteRuleState::Absent)),
            {
                if let Some(ip_from) = self.ip_from.as_ref() {
                    !is_ipv6_addr(ip_from.as_str())
                } else if let Some(ip_to) = self.ip_to.as_ref() {
                    !is_ipv6_addr(ip_to.as_str())
                } else if let Some(family) = self.family.as_ref() {
                    *family == AddressFamily::IPv4
                } else {
                    log::warn!(
                        "Neither ip-from, ip-to nor family \
                        is defined, treating it a IPv4 route rule"
                    );
                    true
                }
            },
            self.table_id
                .unwrap_or(RouteRuleEntry::USE_DEFAULT_ROUTE_TABLE),
            self.ip_from.as_deref().unwrap_or(""),
            self.ip_to.as_deref().unwrap_or(""),
            self.priority
                .unwrap_or(RouteRuleEntry::USE_DEFAULT_PRIORITY),
            self.fwmark.unwrap_or(0),
            self.fwmask.unwrap_or(0),
            self.action.map(u8::from).unwrap_or(0),
            self.suppress_prefix_length.unwrap_or_default(),
        )
    }

    pub(crate) fn sanitize(&mut self) -> Result<(), NmstateError> {
        if let Some(ip) = self.ip_from.as_ref() {
            if ip.is_empty() {
                self.ip_from = None;
            } else {
                let new_ip = sanitize_ip_network(ip)?;
                if self.family.is_none() {
                    match is_ipv6_addr(new_ip.as_str()) {
                        true => self.family = Some(AddressFamily::IPv6),
                        false => self.family = Some(AddressFamily::IPv4),
                    };
                }
                if ip != &new_ip {
                    log::warn!(
                        "Route rule ip-from {} sanitized to {}",
                        ip,
                        new_ip
                    );
                    self.ip_from = Some(new_ip);
                }
            }
        }
        if let Some(ip) = self.ip_to.as_ref() {
            if ip.is_empty() {
                self.ip_to = None;
            } else {
                let new_ip = sanitize_ip_network(ip)?;
                if self.family.is_none() {
                    match is_ipv6_addr(new_ip.as_str()) {
                        true => self.family = Some(AddressFamily::IPv6),
                        false => self.family = Some(AddressFamily::IPv4),
                    };
                }
                if ip != &new_ip {
                    log::warn!(
                        "Route rule ip-to {} sanitized to {}",
                        ip,
                        new_ip
                    );
                    self.ip_to = Some(new_ip);
                }
            }
        }
        self.validate_ip_from_to()?;
        self.validate_fwmark_and_fwmask()?;

        if self.action.is_none() && self.table_id.is_none() {
            log::info!(
                "Route rule {self} has no action or route-table \
                defined, using default route table 254"
            );
            self.table_id = Some(RouteRuleEntry::DEFAULR_ROUTE_TABLE_ID);
        }

        Ok(())
    }
}

// For Vec::dedup()
impl PartialEq for RouteRuleEntry {
    fn eq(&self, other: &Self) -> bool {
        self.sort_key() == other.sort_key()
    }
}

// For Vec::sort_unstable()
impl Ord for RouteRuleEntry {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.sort_key().cmp(&other.sort_key())
    }
}

// For ord
impl Eq for RouteRuleEntry {}

// For ord
impl PartialOrd for RouteRuleEntry {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Hash for RouteRuleEntry {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.sort_key().hash(state);
    }
}

impl std::fmt::Display for RouteRuleEntry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut props = Vec::new();
        if self.is_absent() {
            props.push("state: absent".to_string());
        }
        if let Some(v) = self.family.as_ref() {
            props.push(format!("family: {v}"));
        }
        if let Some(v) = self.ip_from.as_ref() {
            props.push(format!("ip-from: {v}"));
        }
        if let Some(v) = self.ip_to.as_ref() {
            props.push(format!("ip-to: {v}"));
        }
        if let Some(v) = self.priority.as_ref() {
            props.push(format!("priority: {v}"));
        }
        if let Some(v) = self.table_id.as_ref() {
            props.push(format!("route-table: {v}"));
        }
        if let Some(v) = self.fwmask.as_ref() {
            props.push(format!("fwmask: {v}"));
        }
        if let Some(v) = self.fwmark.as_ref() {
            props.push(format!("fwmark: {v}"));
        }
        if let Some(v) = self.iif.as_ref() {
            props.push(format!("iif: {v}"));
        }
        if let Some(v) = self.action.as_ref() {
            props.push(format!("action: {v}"));
        }
        if let Some(v) = self.suppress_prefix_length.as_ref() {
            props.push(format!("suppress-prefix-length: {v}"));
        }
        write!(f, "{}", props.join(" "))
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
pub enum RouteRuleAction {
    Blackhole,
    Unreachable,
    Prohibit,
}

impl std::fmt::Display for RouteRuleAction {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Blackhole => "blackhole",
                Self::Unreachable => "unreachable",
                Self::Prohibit => "prohibit",
            }
        )
    }
}

const FR_ACT_BLACKHOLE: u8 = 6;
const FR_ACT_UNREACHABLE: u8 = 7;
const FR_ACT_PROHIBIT: u8 = 8;

impl From<RouteRuleAction> for u8 {
    fn from(v: RouteRuleAction) -> u8 {
        match v {
            RouteRuleAction::Blackhole => FR_ACT_BLACKHOLE,
            RouteRuleAction::Unreachable => FR_ACT_UNREACHABLE,
            RouteRuleAction::Prohibit => FR_ACT_PROHIBIT,
        }
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MergedRouteRules {
    pub(crate) desired: RouteRules,
    pub(crate) current: RouteRules,
    // The `for_apply` will hold two type of route rule:
    //  * Desired route rules
    //  * Current route rules been marked as absent
    pub(crate) for_apply: Vec<RouteRuleEntry>,
    // The `for_verify` hold the same data as `for_apply` except the
    // auto set priority.
    pub(crate) for_verify: Vec<RouteRuleEntry>,
}

impl MergedRouteRules {
    pub(crate) fn new(
        desired: RouteRules,
        current: RouteRules,
    ) -> Result<Self, NmstateError> {
        let mut for_apply: Vec<RouteRuleEntry> = Vec::new();
        let mut merged_rules: Vec<RouteRuleEntry> = Vec::new();

        let mut des_absent_rules: Vec<&RouteRuleEntry> = Vec::new();
        if let Some(rules) = desired.config.as_ref() {
            for rule in rules.as_slice().iter().filter(|r| r.is_absent()) {
                des_absent_rules.push(rule);
            }
        }

        if let Some(cur_rules) = current.config.as_ref() {
            for rule in cur_rules {
                if des_absent_rules
                    .as_slice()
                    .iter()
                    .any(|absent_rule| absent_rule.is_match(rule))
                {
                    let mut new_rule = rule.clone();
                    new_rule.state = Some(RouteRuleState::Absent);
                    new_rule.sanitize()?;
                    for_apply.push(new_rule);
                } else {
                    merged_rules.push(rule.clone());
                }
            }
        }

        if let Some(rules) = desired.config.as_ref() {
            for rule in rules.as_slice().iter().filter(|r| !r.is_absent()) {
                let mut rule = rule.clone();
                rule.sanitize()?;
                merged_rules.push(rule.clone());
                for_apply.push(rule);
            }
        }

        let for_verify = for_apply.clone();

        set_auto_priority(for_apply.as_mut_slice(), merged_rules.as_slice());

        Ok(Self {
            desired,
            current,
            for_apply,
            for_verify,
        })
    }

    pub(crate) fn remove_rules_to_ignored_ifaces(
        &mut self,
        ignored_ifaces: &[(String, InterfaceType)],
    ) {
        let ignored_ifaces: Vec<&str> = ignored_ifaces
            .iter()
            .filter(|(_, t)| !t.is_userspace())
            .map(|(n, _)| n.as_str())
            .collect();

        self.for_apply.retain(|rule| {
            if let Some(iif) = rule.iif.as_ref() {
                !ignored_ifaces.contains(&iif.as_str())
            } else {
                true
            }
        })
    }

    pub(crate) fn is_changed(&self) -> bool {
        (!self.desired.is_empty())
            && (self.for_apply
                != self.current.config.clone().unwrap_or_default())
    }
}

fn set_auto_priority(
    for_apply: &mut [RouteRuleEntry],
    merged: &[RouteRuleEntry],
) {
    let mut max_priority = get_max_rule_priority(merged);
    if max_priority < ROUTE_RULE_DEFAULT_PRIORIRY - 1 {
        max_priority = ROUTE_RULE_DEFAULT_PRIORIRY - 1;
    }

    for rule in for_apply.iter_mut().filter(|r| {
        !r.is_absent()
            && (r.priority.is_none()
                || r.priority == Some(RouteRuleEntry::USE_DEFAULT_PRIORITY))
    }) {
        max_priority += 1;
        rule.priority = Some(max_priority);
    }
}

fn get_max_rule_priority(rules: &[RouteRuleEntry]) -> i64 {
    rules
        .iter()
        .map(|r| r.priority.unwrap_or_default())
        .max()
        .unwrap_or_default()
}
