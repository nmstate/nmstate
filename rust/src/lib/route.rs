// SPDX-License-Identifier: Apache-2.0

use std::collections::{hash_map::Entry, HashMap, HashSet};
use std::hash::{Hash, Hasher};
use std::net::Ipv4Addr;
use std::str::FromStr;

use serde::{Deserialize, Serialize};

use crate::{
    ip::{is_ipv6_addr, sanitize_ip_network},
    ErrorKind, InterfaceType, MergedInterfaces, NmstateError,
};

const DEFAULT_TABLE_ID: u32 = 254; // main route table ID
const LOOPBACK_IFACE_NAME: &str = "lo";

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
/// IP routing status
pub struct Routes {
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Running effected routes containing route from universe or link scope,
    /// and only from these protocols:
    ///  * boot (often used by `iproute` command)
    ///  * static
    ///  * ra
    ///  * dhcp
    ///  * mrouted
    ///  * keepalived
    ///  * babel
    ///
    /// Ignored when applying.
    pub running: Option<Vec<RouteEntry>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Static routes containing route from universe or link scope,
    /// and only from these protocols:
    ///  * boot (often used by `iproute` command)
    ///  * static
    ///
    /// When applying, `None` means preserve current routes.
    /// This property is not overriding but adding specified routes to
    /// existing routes. To delete a route entry, please [RouteEntry.state] as
    /// [RouteState::Absent]. Any property of absent [RouteEntry] set to
    /// `None` means wildcard. For example, this [crate::NetworkState] could
    /// remove all routes next hop to interface eth1(showing in yaml):
    /// ```yaml
    /// routes:
    ///   config:
    ///   - next-hop-interface: eth1
    ///     state: absent
    /// ```
    ///
    /// To change a route entry, you need to delete old one and add new one(can
    /// be in single transaction).
    pub config: Option<Vec<RouteEntry>>,
}

impl Routes {
    pub fn new() -> Self {
        Self::default()
    }

    /// TODO: hide it, internal only
    pub fn is_empty(&self) -> bool {
        self.running.is_none() && self.config.is_none()
    }

    pub fn validate(&self) -> Result<(), NmstateError> {
        // All desire non-absent route should have next hop interface except
        // for route with route type `Blackhole`, `Unreachable`, `Prohibit`.
        if let Some(config_routes) = self.config.as_ref() {
            for route in config_routes.iter() {
                if !route.is_absent() {
                    if !route.is_unicast()
                        && (route.next_hop_iface.is_some()
                            && route.next_hop_iface
                                != Some(LOOPBACK_IFACE_NAME.to_string())
                            || route.next_hop_addr.is_some())
                    {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "A {:?} Route cannot have a next \
                                hop : {route:?}",
                                route.route_type.unwrap()
                            ),
                        ));
                    } else if route.next_hop_iface.is_none()
                        && route.is_unicast()
                    {
                        return Err(NmstateError::new(
                            ErrorKind::NotImplementedError,
                            format!(
                                "Route with empty next hop interface \
                            is not supported: {route:?}"
                            ),
                        ));
                    }
                }
                validate_route_dst(route)?;
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum RouteState {
    /// Mark a route entry as absent to remove it.
    Absent,
}

impl Default for RouteState {
    fn default() -> Self {
        Self::Absent
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
/// Route entry
pub struct RouteEntry {
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Only used for delete route when applying.
    pub state: Option<RouteState>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Route destination address or network
    /// Mandatory for every non-absent routes.
    pub destination: Option<String>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "next-hop-interface"
    )]
    /// Route next hop interface name.
    /// Serialize and deserialize to/from `next-hop-interface`.
    /// Mandatory for every non-absent routes except for route with
    /// route type `Blackhole`, `Unreachable`, `Prohibit`.
    pub next_hop_iface: Option<String>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "next-hop-address"
    )]
    /// Route next hop IP address.
    /// Serialize and deserialize to/from `next-hop-address`.
    /// When setting this as empty string for absent route, it will only delete
    /// routes __without__ `next-hop-address`.
    pub next_hop_addr: Option<String>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_i64_or_string"
    )]
    /// Route metric. [RouteEntry::USE_DEFAULT_METRIC] for default
    /// setting of network backend.
    pub metric: Option<i64>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Route table id. [RouteEntry::USE_DEFAULT_ROUTE_TABLE] for main
    /// route table 254.
    pub table_id: Option<u32>,

    /// ECMP(Equal-Cost Multi-Path) route weight
    /// The valid range of this property is 1-256.
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u16_or_string"
    )]
    pub weight: Option<u16>,
    /// Route type
    /// Serialize and deserialize to/from `route-type`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub route_type: Option<RouteType>,
    /// Congestion window clamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cwnd: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Route source defines which IP address should be used as the source
    /// for packets routed via a specific route
    pub source: Option<String>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
pub enum RouteType {
    Blackhole,
    Unreachable,
    Prohibit,
}

impl std::fmt::Display for RouteType {
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

const RTN_UNICAST: u8 = 1;
const RTN_BLACKHOLE: u8 = 6;
const RTN_UNREACHABLE: u8 = 7;
const RTN_PROHIBIT: u8 = 8;

impl From<RouteType> for u8 {
    fn from(v: RouteType) -> u8 {
        match v {
            RouteType::Blackhole => RTN_BLACKHOLE,
            RouteType::Unreachable => RTN_UNREACHABLE,
            RouteType::Prohibit => RTN_PROHIBIT,
        }
    }
}

impl RouteEntry {
    pub const USE_DEFAULT_METRIC: i64 = -1;
    pub const USE_DEFAULT_ROUTE_TABLE: u32 = 0;

    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn is_absent(&self) -> bool {
        matches!(self.state, Some(RouteState::Absent))
    }

    /// Whether the desired route (self) matches with another
    /// metric is ignored.
    pub(crate) fn is_match(&self, other: &Self) -> bool {
        if self.destination.as_ref().is_some()
            && self.destination.as_deref() != Some("")
            && self.destination != other.destination
        {
            return false;
        }
        if self.next_hop_iface.as_ref().is_some()
            && self.next_hop_iface != other.next_hop_iface
        {
            return false;
        }

        if self.next_hop_addr.as_ref().is_some()
            && self.next_hop_addr != other.next_hop_addr
        {
            return false;
        }
        if self.table_id.is_some()
            && self.table_id != Some(RouteEntry::USE_DEFAULT_ROUTE_TABLE)
            && self.table_id != other.table_id
        {
            return false;
        }
        if self.weight.is_some() && self.weight != other.weight {
            return false;
        }
        if self.route_type.is_some() && self.route_type != other.route_type {
            return false;
        }
        if self.cwnd.is_some() && self.cwnd != other.cwnd {
            return false;
        }
        if self.source.as_ref().is_some() && self.source != other.source {
            return false;
        }
        true
    }

    // Return tuple of (no_absent, is_ipv4, table_id, next_hop_iface,
    // destination, next_hop_addr, source, weight, cwnd)
    // Metric is ignored
    fn sort_key(&self) -> (bool, bool, u32, &str, &str, &str, &str, u16, u32) {
        (
            !matches!(self.state, Some(RouteState::Absent)),
            !self
                .destination
                .as_ref()
                .map(|d| is_ipv6_addr(d.as_str()))
                .unwrap_or_default(),
            self.table_id.unwrap_or(DEFAULT_TABLE_ID),
            self.next_hop_iface
                .as_deref()
                .unwrap_or(LOOPBACK_IFACE_NAME),
            self.destination.as_deref().unwrap_or(""),
            self.next_hop_addr.as_deref().unwrap_or(""),
            self.source.as_deref().unwrap_or(""),
            self.weight.unwrap_or_default(),
            self.cwnd.unwrap_or_default(),
        )
    }

    pub(crate) fn sanitize(&mut self) -> Result<(), NmstateError> {
        if let Some(dst) = self.destination.as_ref() {
            if dst.is_empty() {
                self.destination = None;
            } else {
                let new_dst = sanitize_ip_network(dst)?;
                if dst != &new_dst {
                    log::warn!(
                        "Route destination {} sanitized to {}",
                        dst,
                        new_dst
                    );
                    self.destination = Some(new_dst);
                }
            }
        }
        if let Some(via) = self.next_hop_addr.as_ref() {
            let new_via = format!("{}", via.parse::<std::net::IpAddr>()?);
            if via != &new_via {
                log::warn!(
                    "Route next-hop-address {} sanitized to {}",
                    via,
                    new_via
                );
                self.next_hop_addr = Some(new_via);
            }
        }
        if let Some(src) = self.source.as_ref() {
            let new_src = format!(
                "{}",
                src.parse::<std::net::IpAddr>().map_err(|e| {
                    NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!("Failed to parse IP address '{}': {}", src, e),
                    )
                })?
            );
            if src != &new_src {
                log::info!(
                    "Route source address {} sanitized to {}",
                    src,
                    new_src
                );
                self.source = Some(new_src);
            }
        }
        if let Some(weight) = self.weight {
            if !(1..=256).contains(&weight) {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Invalid ECMP route weight {weight}, \
                        should be in the range of 1 to 256"
                    ),
                ));
            }
            if let Some(dst) = self.destination.as_deref() {
                if is_ipv6_addr(dst) {
                    return Err(NmstateError::new(
                        ErrorKind::NotSupportedError,
                        "IPv6 ECMP route with weight is not supported yet"
                            .to_string(),
                    ));
                }
            }
        }
        if let Some(cwnd) = self.cwnd {
            if cwnd == 0 {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "The value of 'cwnd' cannot be 0".to_string(),
                ));
            }
        }
        Ok(())
    }

    pub(crate) fn is_ipv6(&self) -> bool {
        self.destination.as_ref().map(|d| is_ipv6_addr(d.as_str()))
            == Some(true)
    }

    pub(crate) fn is_unicast(&self) -> bool {
        self.route_type.is_none()
            || u8::from(self.route_type.unwrap()) == RTN_UNICAST
    }
}

// For Vec::dedup()
impl PartialEq for RouteEntry {
    fn eq(&self, other: &Self) -> bool {
        self.sort_key() == other.sort_key()
    }
}

// For Vec::sort_unstable()
impl Ord for RouteEntry {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.sort_key().cmp(&other.sort_key())
    }
}

// For ord
impl Eq for RouteEntry {}

// For ord
impl PartialOrd for RouteEntry {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Hash for RouteEntry {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.sort_key().hash(state);
    }
}

impl std::fmt::Display for RouteEntry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut props = Vec::new();
        if self.is_absent() {
            props.push("state: absent".to_string());
        }
        if let Some(v) = self.destination.as_ref() {
            props.push(format!("destination: {v}"));
        }
        if let Some(v) = self.next_hop_iface.as_ref() {
            props.push(format!("next-hop-interface: {v}"));
        }
        if let Some(v) = self.next_hop_addr.as_ref() {
            props.push(format!("next-hop-address: {v}"));
        }
        if let Some(v) = self.source.as_ref() {
            props.push(format!("source: {v}"));
        }
        if let Some(v) = self.metric.as_ref() {
            props.push(format!("metric: {v}"));
        }
        if let Some(v) = self.table_id.as_ref() {
            props.push(format!("table-id: {v}"));
        }
        if let Some(v) = self.weight {
            props.push(format!("weight: {v}"));
        }
        if let Some(v) = self.cwnd {
            props.push(format!("cwnd: {v}"));
        }

        write!(f, "{}", props.join(" "))
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MergedRoutes {
    // When all routes next hop to a interface are all marked as absent,
    // the `MergedRoutes.merged` will not have entry for this interface, but
    // interface name is found in `MergedRoutes.route_changed_ifaces`.
    // For backend use incremental route changes, please use
    // `MergedRoutes.changed_routes`.
    pub(crate) merged: HashMap<String, Vec<RouteEntry>>,
    pub(crate) route_changed_ifaces: Vec<String>,
    // The `changed_routes` contains changed routes including those been marked
    // as absent. Not including desired route equal to current route.
    pub(crate) changed_routes: Vec<RouteEntry>,
    pub(crate) desired: Routes,
    pub(crate) current: Routes,
}

impl MergedRoutes {
    pub(crate) fn new(
        desired: Routes,
        current: Routes,
        merged_ifaces: &MergedInterfaces,
    ) -> Result<Self, NmstateError> {
        desired.validate()?;
        let mut desired_routes = Vec::new();
        if let Some(rts) = desired.config.as_ref() {
            for rt in rts {
                let mut rt = rt.clone();
                rt.sanitize()?;
                desired_routes.push(rt);
            }
        }

        let mut changed_ifaces: HashSet<&str> = HashSet::new();
        let mut changed_routes: HashSet<RouteEntry> = HashSet::new();

        let ifaces_marked_as_absent: Vec<&str> = merged_ifaces
            .kernel_ifaces
            .values()
            .filter(|i| i.merged.is_absent())
            .map(|i| i.merged.name())
            .collect();

        let ifaces_with_ipv4_disabled: Vec<&str> = merged_ifaces
            .kernel_ifaces
            .values()
            .filter(|i| !i.merged.base_iface().is_ipv4_enabled())
            .map(|i| i.merged.name())
            .collect();

        let ifaces_with_ipv6_disabled: Vec<&str> = merged_ifaces
            .kernel_ifaces
            .values()
            .filter(|i| !i.merged.base_iface().is_ipv6_enabled())
            .map(|i| i.merged.name())
            .collect();

        // Interface has route added.
        for rt in desired_routes
            .as_slice()
            .iter()
            .filter(|rt| !rt.is_absent())
        {
            if let Some(via) = rt.next_hop_iface.as_ref() {
                if ifaces_marked_as_absent.contains(&via.as_str()) {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "The next hop interface of desired Route '{rt}' \
                            has been marked as absent"
                        ),
                    ));
                }
                if rt.is_ipv6()
                    && ifaces_with_ipv6_disabled.contains(&via.as_str())
                {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "The next hop interface of desired Route '{rt}' \
                            has been marked as IPv6 disabled"
                        ),
                    ));
                }
                if (!rt.is_ipv6())
                    && ifaces_with_ipv4_disabled.contains(&via.as_str())
                {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "The next hop interface of desired Route '{rt}' \
                            has been marked as IPv4 disabled"
                        ),
                    ));
                }
                changed_ifaces.insert(via.as_str());
            } else if rt.route_type.is_some() {
                changed_ifaces.insert(LOOPBACK_IFACE_NAME);
            }
        }

        // Interface has route deleted.
        for absent_rt in
            desired_routes.as_slice().iter().filter(|rt| rt.is_absent())
        {
            if let Some(cur_rts) = current.config.as_ref() {
                for rt in cur_rts {
                    if absent_rt.is_match(rt) {
                        if let Some(via) = rt.next_hop_iface.as_ref() {
                            changed_ifaces.insert(via.as_str());
                        } else {
                            changed_ifaces.insert(LOOPBACK_IFACE_NAME);
                        }
                    }
                }
            }
        }

        let mut merged_routes: Vec<RouteEntry> = Vec::new();

        if let Some(cur_rts) = current.config.as_ref() {
            for rt in cur_rts {
                if let Some(via) = rt.next_hop_iface.as_ref() {
                    // We include current route to merged_routes when it is
                    // not marked as absent due to absent interface or disabled
                    // ip stack or route state:absent.
                    if ifaces_marked_as_absent.contains(&via.as_str())
                        || (rt.is_ipv6()
                            && ifaces_with_ipv6_disabled
                                .contains(&via.as_str()))
                        || (!rt.is_ipv6()
                            && ifaces_with_ipv4_disabled
                                .contains(&via.as_str()))
                        || desired_routes
                            .as_slice()
                            .iter()
                            .filter(|r| r.is_absent())
                            .any(|absent_rt| absent_rt.is_match(rt))
                    {
                        let mut new_rt = rt.clone();
                        new_rt.state = Some(RouteState::Absent);
                        changed_routes.insert(new_rt);
                    } else {
                        merged_routes.push(rt.clone());
                    }
                }
            }
        }

        // Append desired routes
        for rt in desired_routes
            .as_slice()
            .iter()
            .filter(|rt| !rt.is_absent())
        {
            if let Some(cur_rts) = current.config.as_ref() {
                if !cur_rts.as_slice().iter().any(|cur_rt| cur_rt.is_match(rt))
                {
                    changed_routes.insert(rt.clone());
                }
            }
            merged_routes.push(rt.clone());
        }

        merged_routes.sort_unstable();
        merged_routes.dedup();

        let mut merged: HashMap<String, Vec<RouteEntry>> = HashMap::new();

        for rt in merged_routes {
            if let Some(via) = rt.next_hop_iface.as_ref() {
                let rts: &mut Vec<RouteEntry> =
                    match merged.entry(via.to_string()) {
                        Entry::Occupied(o) => o.into_mut(),
                        Entry::Vacant(v) => v.insert(Vec::new()),
                    };
                rts.push(rt);
            } else if rt.route_type.is_some() {
                let rts: &mut Vec<RouteEntry> =
                    match merged.entry(LOOPBACK_IFACE_NAME.to_string()) {
                        Entry::Occupied(o) => o.into_mut(),
                        Entry::Vacant(v) => v.insert(Vec::new()),
                    };
                rts.push(rt);
            }
        }

        let route_changed_ifaces: Vec<String> =
            changed_ifaces.iter().map(|i| i.to_string()).collect();

        Ok(Self {
            merged,
            desired,
            current,
            route_changed_ifaces,
            changed_routes: changed_routes.drain().collect(),
        })
    }

    pub(crate) fn remove_routes_to_ignored_ifaces(
        &mut self,
        ignored_ifaces: &[(String, InterfaceType)],
    ) {
        let ignored_ifaces: Vec<&str> = ignored_ifaces
            .iter()
            .filter_map(|(n, t)| {
                if !t.is_userspace() {
                    Some(n.as_str())
                } else {
                    None
                }
            })
            .collect();

        for iface in ignored_ifaces.as_slice() {
            self.merged.remove(*iface);
        }
        self.route_changed_ifaces
            .retain(|n| !ignored_ifaces.contains(&n.as_str()));
    }

    pub(crate) fn is_changed(&self) -> bool {
        !self.route_changed_ifaces.is_empty()
    }
}

// Validating if the route destination network is valid,
// 0.0.0.0/8 and its subnet cannot be used as the route destination network
// for unicast route
fn validate_route_dst(route: &RouteEntry) -> Result<(), NmstateError> {
    if let Some(dst) = route.destination.as_deref() {
        if !is_ipv6_addr(dst) {
            let ip_net: Vec<&str> = dst.split('/').collect();
            let ip_addr = Ipv4Addr::from_str(ip_net[0])?;
            if ip_addr.octets()[0] == 0 {
                if dst.contains('/') {
                    let prefix = match ip_net[1].parse::<i32>() {
                        Ok(p) => p,
                        Err(_) => {
                            return Err(NmstateError::new(
                                ErrorKind::InvalidArgument,
                                format!(
                                    "The prefix of the route destination network \
                                    '{dst}' is invalid"
                                ),
                            ));
                        }
                    };
                    if prefix >= 8 && route.is_unicast() {
                        let e = NmstateError::new(
                            ErrorKind::InvalidArgument,
                            "0.0.0.0/8 and its subnet cannot be used as \
                            the route destination for unicast route, please use \
                            the default gateway 0.0.0.0/0 instead"
                                .to_string(),
                        );
                        log::error!("{}", e);
                        return Err(e);
                    }
                } else if route.is_unicast() {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        "0.0.0.0/8 and its subnet cannot be used as \
                        the route destination for unicast route, please use \
                        the default gateway 0.0.0.0/0 instead"
                            .to_string(),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
            return Ok(());
        }
    }
    Ok(())
}
