use std::collections::{hash_map::Entry, HashMap, HashSet};
use std::convert::TryFrom;

use serde::{Deserialize, Serialize};

use crate::{
    ip::{is_ipv6_addr, sanitize_ip_network, AddressFamily},
    ErrorKind, InterfaceIpAddr, NmstateError,
};

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

    // * Neither ip_from nor ip_to should be defined
    pub(crate) fn validate(&self) -> Result<(), NmstateError> {
        if let Some(rules) = self.config.as_ref() {
            for rule in rules.iter().filter(|r| !r.is_absent()) {
                rule.validate()?;
            }
        }
        Ok(())
    }

    // * desired absent route rule is removed unless another matching rule been
    //   added.
    // * desired static rule exists.
    /// TODO: Hide it, internal use only
    pub fn verify(&self, current: &Self) -> Result<(), NmstateError> {
        if let Some(rules) = self.config.as_ref() {
            let mut rules = rules.clone();
            for rule in rules.iter_mut() {
                rule.sanitize().ok();
            }

            let empty_vec: Vec<RouteRuleEntry> = Vec::new();
            let cur_rules = match current.config.as_deref() {
                Some(c) => c,
                None => empty_vec.as_slice(),
            };
            for rule in rules.iter().filter(|r| !r.is_absent()) {
                if !cur_rules.iter().any(|r| rule.is_match(r)) {
                    let e = NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Desired route rule {:?} not found after apply",
                            rule
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }

            for absent_rule in rules.iter().filter(|r| r.is_absent()) {
                // We ignore absent rule if user is replacing old rule
                // with new one.
                if rules
                    .iter()
                    .any(|r| (!r.is_absent()) && absent_rule.is_match(r))
                {
                    continue;
                }

                if let Some(cur_rule) =
                    cur_rules.iter().find(|r| absent_rule.is_match(r))
                {
                    let e = NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Desired absent route rule {:?} still found \
                            after apply: {:?}",
                            absent_rule, cur_rule
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
        }
        Ok(())
    }

    // RouteRuleEntry been added/removed for specific table id , all(including
    // desire and current) its rules will be included in return hash.
    // Steps:
    //  1. Find out all table id with desired add rules.
    //  2. Find out all table id impacted by desired absent rules.
    //  3. Copy all rules from current which are to changed table id.
    //  4. Remove rules base on absent.
    //  5. Add rules in desire.
    //  6. Sort and remove duplicate rule.
    pub(crate) fn gen_rule_changed_table_ids(
        &self,
        current: &Self,
    ) -> Result<HashMap<u32, Vec<RouteRuleEntry>>, NmstateError> {
        let mut ret: HashMap<u32, Vec<RouteRuleEntry>> = HashMap::new();
        let cur_rules_index = current
            .config
            .as_ref()
            .map(|c| create_rule_index_by_table_id(c.as_slice()))
            .unwrap_or_default();
        let mut desired_rules =
            self.config.as_ref().cloned().unwrap_or_default();
        for rule in desired_rules.iter_mut() {
            rule.sanitize()?;
        }
        let des_rules_index =
            create_rule_index_by_table_id(desired_rules.as_slice());

        let mut table_ids_in_desire: HashSet<u32> =
            des_rules_index.keys().copied().collect();

        // Convert the absent rule without table id to multiple
        // rules with table_id define.
        let absent_rules = flat_absent_rule(
            self.config.as_deref().unwrap_or(&[]),
            current.config.as_deref().unwrap_or(&[]),
        );

        // Include table id which will be impacted by absent rules
        for absent_rule in &absent_rules {
            if let Some(i) = absent_rule.table_id {
                log::debug!(
                    "Route table is impacted by absent rule {:?}",
                    absent_rule
                );
                table_ids_in_desire.insert(i);
            }
        }

        // Copy current rules of desired route table
        for table_id in &table_ids_in_desire {
            if let Some(cur_rules) = cur_rules_index.get(table_id) {
                ret.insert(
                    *table_id,
                    cur_rules
                        .as_slice()
                        .iter()
                        .map(|r| (*r).clone())
                        .collect::<Vec<RouteRuleEntry>>(),
                );
            }
        }

        // Apply absent rules
        for absent_rule in &absent_rules {
            // All absent_rule should have table id here
            if let Some(table_id) = absent_rule.table_id.as_ref() {
                if let Some(rules) = ret.get_mut(table_id) {
                    rules.retain(|r| !absent_rule.is_match(r));
                }
            }
        }

        // Append desire rules
        for (table_id, desire_rules) in des_rules_index.iter() {
            let new_rules = desire_rules
                .iter()
                .map(|r| (*r).clone())
                .collect::<Vec<RouteRuleEntry>>();
            match ret.entry(*table_id) {
                Entry::Occupied(o) => {
                    o.into_mut().extend(new_rules);
                }
                Entry::Vacant(v) => {
                    v.insert(new_rules);
                }
            };
        }

        // Sort and remove the duplicated rules
        for desire_rules in ret.values_mut() {
            desire_rules.sort_unstable();
            desire_rules.dedup();
        }

        Ok(ret)
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
    pub ip_from: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Destination prefix to match.
    /// Serialize and deserialize to/from `ip-to`.
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

    pub(crate) fn validate(&self) -> Result<(), NmstateError> {
        if self.ip_from.is_none()
            && self.ip_to.is_none()
            && self.family.is_none()
        {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Neither ip-from, ip-to nor family is defined {:?}",
                    self
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
                        format!("The ip-from format mismatches with the family set {:?}",
                                self
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
                        format!("The ip-to format mismatches with the family set {:?}",
                                self
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
        }
        if self.fwmark.is_none() && self.fwmask.is_some() {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!("fwmask is present but fwmark is not defined or is zero {:?}",
                        self
                ),
            );
            log::error!("{}", e);
            return Err(e);
        }
        Ok(())
    }

    fn is_absent(&self) -> bool {
        matches!(self.state, Some(RouteRuleState::Absent))
    }

    fn is_match(&self, other: &Self) -> bool {
        if let Some(ip_from) = self.ip_from.as_deref() {
            let ip_from = if !ip_from.contains('/') {
                match InterfaceIpAddr::try_from(ip_from) {
                    Ok(ref i) => i.into(),
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
        }
        if let Some(ip_to) = self.ip_to.as_deref() {
            let ip_to = if !ip_to.contains('/') {
                match InterfaceIpAddr::try_from(ip_to) {
                    Ok(ref i) => i.into(),
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
        }
        if self.priority.is_some()
            && self.priority != Some(RouteRuleEntry::USE_DEFAULT_PRIORITY)
            && self.priority != other.priority
        {
            return false;
        }
        if self.table_id.is_some()
            && self.table_id != Some(RouteRuleEntry::USE_DEFAULT_ROUTE_TABLE)
            && self.table_id != other.table_id
        {
            return false;
        }
        if self.fwmark.is_some() && self.fwmark != other.fwmark {
            return false;
        }
        if self.fwmask.is_some() && self.fwmask != other.fwmask {
            return false;
        }
        true
    }

    // Return tuple of (no_absent, is_ipv4, table_id, ip_from,
    // ip_to, priority, fwmark, fwmask)
    fn sort_key(&self) -> (bool, bool, u32, &str, &str, i64, u32, u32) {
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
        )
    }

    pub(crate) fn sanitize(&mut self) -> Result<(), NmstateError> {
        if let Some(ip) = self.ip_from.as_ref() {
            let new_ip = sanitize_ip_network(ip)?;
            if self.family.is_none() {
                match is_ipv6_addr(new_ip.as_str()) {
                    true => self.family = Some(AddressFamily::IPv6),
                    false => self.family = Some(AddressFamily::IPv4),
                };
            }
            if ip != &new_ip {
                log::warn!("Route rule ip-from {} sanitized to {}", ip, new_ip);
                self.ip_from = Some(new_ip);
            }
        }
        if let Some(ip) = self.ip_to.as_ref() {
            let new_ip = sanitize_ip_network(ip)?;
            if self.family.is_none() {
                match is_ipv6_addr(new_ip.as_str()) {
                    true => self.family = Some(AddressFamily::IPv6),
                    false => self.family = Some(AddressFamily::IPv4),
                };
            }
            if ip != &new_ip {
                log::warn!("Route rule ip-to {} sanitized to {}", ip, new_ip);
                self.ip_to = Some(new_ip);
            }
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

// Absent rule will be ignored
fn create_rule_index_by_table_id(
    rules: &[RouteRuleEntry],
) -> HashMap<u32, Vec<&RouteRuleEntry>> {
    let mut ret: HashMap<u32, Vec<&RouteRuleEntry>> = HashMap::new();
    for rule in rules {
        if rule.is_absent() {
            continue;
        }
        let table_id = match rule.table_id {
            Some(RouteRuleEntry::USE_DEFAULT_ROUTE_TABLE) | None => {
                RouteRuleEntry::DEFAULR_ROUTE_TABLE_ID
            }
            Some(i) => i,
        };
        match ret.entry(table_id) {
            Entry::Occupied(o) => {
                o.into_mut().push(rule);
            }
            Entry::Vacant(v) => {
                v.insert(vec![rule]);
            }
        };
    }
    ret
}

// All the rules sending to this function has no table id defined.
fn flat_absent_rule(
    desire_rules: &[RouteRuleEntry],
    cur_rules: &[RouteRuleEntry],
) -> Vec<RouteRuleEntry> {
    let mut ret: Vec<RouteRuleEntry> = Vec::new();
    for absent_rule in desire_rules.iter().filter(|r| r.is_absent()) {
        if absent_rule.table_id.is_none() {
            for cur_rule in cur_rules {
                if absent_rule.is_match(cur_rule) {
                    let mut new_absent_rule = absent_rule.clone();
                    new_absent_rule.table_id = cur_rule.table_id;
                    ret.push(new_absent_rule);
                }
            }
        } else {
            ret.push(absent_rule.clone());
        }
    }
    ret
}
