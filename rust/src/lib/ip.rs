use std::net::IpAddr;
use std::str::FromStr;

use serde::{self, Deserialize, Deserializer, Serialize};

use crate::{
    BaseInterface, DnsClientState, ErrorKind, Interfaces, NmstateError,
};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
struct InterfaceIp {
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub enabled: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub dhcp: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub autoconf: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "dhcp-client-id"
    )]
    pub dhcp_client_id: Option<Dhcpv4ClientId>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "dhcp-duid")]
    pub dhcp_duid: Option<Dhcpv6Duid>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "address")]
    pub addresses: Option<Vec<InterfaceIpAddr>>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "auto-dns",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub auto_dns: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "auto-gateway",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub auto_gateway: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "auto-routes",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub auto_routes: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "auto-route-table-id",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub auto_table_id: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "addr-gen-mode")]
    pub addr_gen_mode: Option<Ipv6AddrGenMode>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Default)]
#[serde(into = "InterfaceIp")]
#[non_exhaustive]
pub struct InterfaceIpv4 {
    pub enabled: bool,
    pub(crate) prop_list: Vec<&'static str>,
    pub dhcp: Option<bool>,
    pub dhcp_client_id: Option<Dhcpv4ClientId>,
    pub addresses: Option<Vec<InterfaceIpAddr>>,
    pub(crate) dns: Option<DnsClientState>,
    pub auto_dns: Option<bool>,
    pub auto_gateway: Option<bool>,
    pub auto_routes: Option<bool>,
    pub auto_table_id: Option<u32>,
}

impl InterfaceIpv4 {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn is_auto(&self) -> bool {
        self.enabled && self.dhcp == Some(true)
    }

    pub(crate) fn update(&mut self, other: &Self) {
        if other.prop_list.contains(&"enabled") {
            self.enabled = other.enabled;
        }

        if other.prop_list.contains(&"dhcp") {
            self.dhcp = other.dhcp;
        }
        if other.prop_list.contains(&"dhcp_client_id") {
            self.dhcp_client_id = other.dhcp_client_id.clone();
        }
        if other.prop_list.contains(&"addresses") {
            self.addresses = other.addresses.clone();
        }
        if other.prop_list.contains(&"dns") {
            self.dns = other.dns.clone();
        }
        if other.prop_list.contains(&"auto_dns") {
            self.auto_dns = other.auto_dns;
        }
        if other.prop_list.contains(&"auto_gateway") {
            self.auto_gateway = other.auto_gateway;
        }
        if other.prop_list.contains(&"auto_routes") {
            self.auto_routes = other.auto_routes;
        }
        if other.prop_list.contains(&"auto_table_id") {
            self.auto_table_id = other.auto_table_id;
        }

        for other_prop_name in &other.prop_list {
            if !self.prop_list.contains(other_prop_name) {
                self.prop_list.push(other_prop_name);
            }
        }
        self.cleanup()
    }

    // * Disable DHCP and remove address if enabled: false
    // * Set DHCP options to None if DHCP is false
    fn cleanup(&mut self) {
        if !self.enabled {
            self.dhcp = None;
            self.addresses = None;
        }

        if self.dhcp != Some(true) {
            self.auto_dns = None;
            self.auto_gateway = None;
            self.auto_routes = None;
            self.auto_table_id = None;
        }
    }

    // Clean up before sending to plugin for applying
    // * Set auto_dns, auto_gateway and auto_routes to true if DHCP enabled and
    //   those options is None
    // * Remove static IP address when DHCP enabled.
    pub(crate) fn pre_edit_cleanup(&mut self) {
        if self.is_auto() {
            if self.auto_dns.is_none() {
                self.auto_dns = Some(true);
            }
            if self.auto_routes.is_none() {
                self.auto_routes = Some(true);
            }
            if self.auto_gateway.is_none() {
                self.auto_gateway = Some(true);
            }
            if !self.addresses.as_deref().unwrap_or_default().is_empty() {
                log::warn!(
                    "Static addresses {:?} are ignored when dynamic \
                    IP is enabled",
                    self.addresses.as_deref().unwrap_or_default()
                );
                self.addresses = None;
            }
        }
        self.cleanup();
    }

    // Clean up before verification
    // * Sort IP address
    // * Ignore DHCP options if DHCP disabled
    // * Ignore address if DHCP enabled
    // * Set DHCP as off if enabled and dhcp is None
    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.cleanup();
        if self.dhcp == Some(true) {
            self.addresses = None;
        }
        if let Some(addrs) = self.addresses.as_mut() {
            addrs.sort_unstable_by(|a, b| {
                (&a.ip, a.prefix_length).cmp(&(&b.ip, b.prefix_length))
            })
        };
        if self.dhcp != Some(true) {
            self.dhcp = Some(false);
        }
    }
}

impl<'de> Deserialize<'de> for InterfaceIpv4 {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let v = serde_json::Value::deserialize(deserializer)?;

        let prop_list = if let Some(v_map) = v.as_object() {
            get_ip_prop_list(v_map)
        } else {
            Vec::new()
        };
        if prop_list.contains(&"autoconf") {
            return Err(serde::de::Error::custom(
                "autoconf is not allowed for IPv4",
            ));
        }
        if prop_list.contains(&"dhcp_duid") {
            return Err(serde::de::Error::custom(
                "dhcp-duid is not allowed for IPv4",
            ));
        }

        let ip: InterfaceIp = match serde_json::from_value(v) {
            Ok(i) => i,
            Err(e) => {
                return Err(serde::de::Error::custom(format!("{}", e)));
            }
        };
        let mut ret = Self::from(ip);
        ret.prop_list = prop_list;
        Ok(ret)
    }
}

impl From<InterfaceIp> for InterfaceIpv4 {
    fn from(ip: InterfaceIp) -> Self {
        Self {
            enabled: ip.enabled.unwrap_or_default(),
            dhcp: ip.dhcp,
            addresses: ip.addresses,
            dhcp_client_id: ip.dhcp_client_id,
            auto_dns: ip.auto_dns,
            auto_routes: ip.auto_routes,
            auto_gateway: ip.auto_gateway,
            auto_table_id: ip.auto_table_id,
            ..Default::default()
        }
    }
}

impl From<InterfaceIpv4> for InterfaceIp {
    fn from(ip: InterfaceIpv4) -> Self {
        let enabled = if ip.prop_list.contains(&"enabled") {
            Some(ip.enabled)
        } else {
            None
        };
        Self {
            enabled,
            dhcp: ip.dhcp,
            addresses: ip.addresses,
            dhcp_client_id: ip.dhcp_client_id,
            auto_dns: ip.auto_dns,
            auto_routes: ip.auto_routes,
            auto_gateway: ip.auto_gateway,
            auto_table_id: ip.auto_table_id,
            ..Default::default()
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize)]
#[non_exhaustive]
#[serde(into = "InterfaceIp")]
pub struct InterfaceIpv6 {
    pub enabled: bool,
    pub(crate) prop_list: Vec<&'static str>,
    pub dhcp: Option<bool>,
    pub dhcp_duid: Option<Dhcpv6Duid>,
    pub autoconf: Option<bool>,
    pub addr_gen_mode: Option<Ipv6AddrGenMode>,
    pub addresses: Option<Vec<InterfaceIpAddr>>,
    pub(crate) dns: Option<DnsClientState>,
    pub auto_dns: Option<bool>,
    pub auto_gateway: Option<bool>,
    pub auto_routes: Option<bool>,
    pub auto_table_id: Option<u32>,
}

impl InterfaceIpv6 {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn is_auto(&self) -> bool {
        self.enabled && (self.dhcp == Some(true) || self.autoconf == Some(true))
    }

    // * Disable DHCP and remove address if enabled: false
    // * Set DHCP options to None if DHCP is false
    fn cleanup(&mut self) {
        if !self.enabled {
            self.dhcp = None;
            self.autoconf = None;
            self.addresses = None;
        }

        if !self.is_auto() {
            self.auto_dns = None;
            self.auto_gateway = None;
            self.auto_routes = None;
            self.auto_table_id = None;
        }
    }

    pub(crate) fn update(&mut self, other: &Self) {
        if other.prop_list.contains(&"enabled") {
            self.enabled = other.enabled;
        }
        if other.prop_list.contains(&"dhcp") {
            self.dhcp = other.dhcp;
        }
        if other.prop_list.contains(&"dhcp_duid") {
            self.dhcp_duid = other.dhcp_duid.clone();
        }
        if other.prop_list.contains(&"autoconf") {
            self.autoconf = other.autoconf;
        }
        if other.prop_list.contains(&"addr_gen_mode") {
            self.addr_gen_mode = other.addr_gen_mode.clone();
        }
        if other.prop_list.contains(&"addresses") {
            self.addresses = other.addresses.clone();
        }
        if other.prop_list.contains(&"auto_dns") {
            self.auto_dns = other.auto_dns;
        }
        if other.prop_list.contains(&"auto_gateway") {
            self.auto_gateway = other.auto_gateway;
        }
        if other.prop_list.contains(&"auto_routes") {
            self.auto_routes = other.auto_routes;
        }
        if other.prop_list.contains(&"auto_table_id") {
            self.auto_table_id = other.auto_table_id;
        }
        if other.prop_list.contains(&"dns") {
            self.dns = other.dns.clone();
        }
        if other.prop_list.contains(&"addr_gen_mode") {
            self.addr_gen_mode = other.addr_gen_mode.clone();
        }
        for other_prop_name in &other.prop_list {
            if !self.prop_list.contains(other_prop_name) {
                self.prop_list.push(other_prop_name);
            }
        }
        self.cleanup()
    }

    // Clean up before verification
    // * Remove link-local address
    // * Ignore DHCP options if DHCP disabled
    // * Ignore IP address when DHCP/autoconf enabled.
    // * Set DHCP None to Some(false)
    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.cleanup();
        if self.is_auto() {
            self.addresses = None;
        }
        if let Some(addrs) = self.addresses.as_mut() {
            addrs.retain(|addr| {
                !is_ipv6_unicast_link_local(
                    &addr.ip.to_string(),
                    addr.prefix_length,
                )
            })
        };
        if let Some(addrs) = self.addresses.as_mut() {
            addrs.sort_unstable_by(|a, b| {
                (&a.ip, a.prefix_length).cmp(&(&b.ip, b.prefix_length))
            })
        };
        if self.dhcp != Some(true) {
            self.dhcp = Some(false);
        }
        if self.autoconf != Some(true) {
            self.autoconf = Some(false);
        }
    }

    // Clean up before Apply
    // * Remove link-local address
    // * Set auto_dns, auto_gateway and auto_routes to true if DHCP/autoconf
    //   enabled and those options is None
    // * Remove static IP address when DHCP/autoconf enabled.
    pub(crate) fn pre_edit_cleanup(&mut self) {
        if let Some(addrs) = self.addresses.as_mut() {
            addrs.retain(|addr| {
                if is_ipv6_unicast_link_local(
                    &addr.ip.to_string(),
                    addr.prefix_length,
                ) {
                    log::warn!(
                        "Ignoring IPv6 link local address {}/{}",
                        &addr.ip,
                        addr.prefix_length
                    );
                    false
                } else {
                    true
                }
            })
        };
        if self.is_auto() {
            if self.auto_dns.is_none() {
                self.auto_dns = Some(true);
            }
            if self.auto_routes.is_none() {
                self.auto_routes = Some(true);
            }
            if self.auto_gateway.is_none() {
                self.auto_gateway = Some(true);
            }
            if !self.addresses.as_deref().unwrap_or_default().is_empty() {
                log::warn!(
                    "Static addresses {:?} are ignored when dynamic \
                    IP is enabled",
                    self.addresses.as_deref().unwrap_or_default()
                );
                self.addresses = None;
            }
        }
        self.cleanup();
    }
}

impl<'de> Deserialize<'de> for InterfaceIpv6 {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let v = serde_json::Value::deserialize(deserializer)?;

        let prop_list = if let Some(v_map) = v.as_object() {
            get_ip_prop_list(v_map)
        } else {
            Vec::new()
        };
        if prop_list.contains(&"dhcp_client_id") {
            return Err(serde::de::Error::custom(
                "dhcp-client-id is not allowed for IPv6",
            ));
        }
        let ip: InterfaceIp = match serde_json::from_value(v) {
            Ok(i) => i,
            Err(e) => {
                return Err(serde::de::Error::custom(format!("{}", e)));
            }
        };
        let mut ret = Self::from(ip);
        ret.prop_list = prop_list;
        Ok(ret)
    }
}

impl From<InterfaceIp> for InterfaceIpv6 {
    fn from(ip: InterfaceIp) -> Self {
        Self {
            enabled: ip.enabled.unwrap_or_default(),
            dhcp: ip.dhcp,
            autoconf: ip.autoconf,
            addresses: ip.addresses,
            dhcp_duid: ip.dhcp_duid,
            auto_dns: ip.auto_dns,
            auto_routes: ip.auto_routes,
            auto_gateway: ip.auto_gateway,
            auto_table_id: ip.auto_table_id,
            addr_gen_mode: ip.addr_gen_mode,
            ..Default::default()
        }
    }
}

impl From<InterfaceIpv6> for InterfaceIp {
    fn from(ip: InterfaceIpv6) -> Self {
        let enabled = if ip.prop_list.contains(&"enabled") {
            Some(ip.enabled)
        } else {
            None
        };
        Self {
            enabled,
            dhcp: ip.dhcp,
            autoconf: ip.autoconf,
            addresses: ip.addresses,
            dhcp_duid: ip.dhcp_duid,
            auto_dns: ip.auto_dns,
            auto_routes: ip.auto_routes,
            auto_gateway: ip.auto_gateway,
            auto_table_id: ip.auto_table_id,
            addr_gen_mode: ip.addr_gen_mode,
            ..Default::default()
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct InterfaceIpAddr {
    pub ip: IpAddr,
    #[serde(deserialize_with = "crate::deserializer::u8_or_string")]
    pub prefix_length: u8,
}

impl Default for InterfaceIpAddr {
    fn default() -> Self {
        Self {
            ip: IpAddr::V6(std::net::Ipv6Addr::new(0, 0, 0, 0, 0, 0, 0, 1)),
            prefix_length: 128,
        }
    }
}

pub(crate) fn is_ipv6_addr(addr: &str) -> bool {
    addr.contains(':')
}

// TODO: Rust offical has std::net::Ipv6Addr::is_unicast_link_local() in
// experimental.
fn is_ipv6_unicast_link_local(ip: &str, prefix: u8) -> bool {
    // The unicast link local address range is fe80::/10.
    is_ipv6_addr(ip)
        && ip.len() >= 3
        && ["fe8", "fe9", "fea", "feb"].contains(&&ip[..3])
        && prefix >= 10
}

impl std::convert::TryFrom<&str> for InterfaceIpAddr {
    type Error = NmstateError;
    fn try_from(value: &str) -> Result<Self, Self::Error> {
        let mut addr: Vec<&str> = value.split('/').collect();
        addr.resize(2, "");
        let ip = IpAddr::from_str(addr[0]).map_err(|e| {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!("Invalid IP address {}: {}", addr[0], e),
            );
            log::error!("{}", e);
            e
        })?;

        let prefix_length = if addr[1].is_empty() {
            if ip.is_ipv6() {
                128
            } else {
                32
            }
        } else {
            addr[1].parse::<u8>().map_err(|parse_error| {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!("Invalid IP address {}: {}", value, parse_error),
                );
                log::error!("{}", e);
                e
            })?
        };
        Ok(Self { ip, prefix_length })
    }
}

impl std::convert::From<&InterfaceIpAddr> for String {
    fn from(v: &InterfaceIpAddr) -> String {
        format!("{}/{}", &v.ip, v.prefix_length)
    }
}

pub(crate) fn include_current_ip_address_if_dhcp_on_to_off(
    chg_net_state: &mut Interfaces,
    current: &Interfaces,
) {
    for (iface_name, iface) in chg_net_state.kernel_ifaces.iter_mut() {
        let cur_iface = if let Some(c) = current.kernel_ifaces.get(iface_name) {
            c
        } else {
            continue;
        };
        if let Some(cur_ip_conf) = cur_iface.base_iface().ipv4.as_ref() {
            if cur_ip_conf.is_auto() && cur_ip_conf.addresses.is_some() {
                if let Some(ip_conf) = iface.base_iface_mut().ipv4.as_mut() {
                    if ip_conf.enabled
                        && !ip_conf.is_auto()
                        && ip_conf.addresses.is_none()
                    {
                        ip_conf.addresses = cur_ip_conf.addresses.clone();
                    }
                }
            }
        }
        if let Some(cur_ip_conf) = cur_iface.base_iface().ipv6.as_ref() {
            if cur_ip_conf.is_auto() && cur_ip_conf.addresses.is_some() {
                if let Some(ip_conf) = iface.base_iface_mut().ipv6.as_mut() {
                    if ip_conf.enabled
                        && !ip_conf.is_auto()
                        && ip_conf.addresses.is_none()
                    {
                        ip_conf.addresses = cur_ip_conf.addresses.clone();
                    }
                }
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(from = "String", into = "String")]
pub enum Dhcpv4ClientId {
    LinkLayerAddress,
    // RFC 4361 type 255, 32 bits IAID followed by DUID.
    IaidPlusDuid,
    // hex string or backend specific client id type
    Other(String),
}

impl std::fmt::Display for Dhcpv4ClientId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", String::from(self.clone()))
    }
}

impl From<String> for Dhcpv4ClientId {
    fn from(s: String) -> Self {
        return match s.as_str() {
            "ll" | "LL" => Self::LinkLayerAddress,
            "iaid+duid" | "IAID+DUID" => Self::IaidPlusDuid,
            _ => Self::Other(s),
        };
    }
}

impl From<Dhcpv4ClientId> for String {
    fn from(v: Dhcpv4ClientId) -> Self {
        match v {
            Dhcpv4ClientId::LinkLayerAddress => "ll".to_string(),
            Dhcpv4ClientId::IaidPlusDuid => "iaid+duid".to_string(),
            Dhcpv4ClientId::Other(s) => s,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(from = "String", into = "String")]
pub enum Dhcpv6Duid {
    LinkLayerAddressPlusTime,
    EnterpriseNumber,
    LinkLayerAddress,
    Uuid,
    Other(String),
}

impl std::fmt::Display for Dhcpv6Duid {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", String::from(self.clone()))
    }
}

impl From<String> for Dhcpv6Duid {
    fn from(s: String) -> Self {
        return match s.as_str() {
            "llt" | "LLT" => Self::LinkLayerAddressPlusTime,
            "en" | "EN" => Self::EnterpriseNumber,
            "ll" | "LL" => Self::LinkLayerAddress,
            "uuid" | "UUID" => Self::Uuid,
            _ => Self::Other(s),
        };
    }
}

impl From<Dhcpv6Duid> for String {
    fn from(v: Dhcpv6Duid) -> Self {
        match v {
            Dhcpv6Duid::LinkLayerAddressPlusTime => "llt".to_string(),
            Dhcpv6Duid::EnterpriseNumber => "en".to_string(),
            Dhcpv6Duid::LinkLayerAddress => "ll".to_string(),
            Dhcpv6Duid::Uuid => "uuid".to_string(),
            Dhcpv6Duid::Other(s) => s,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(from = "String", into = "String")]
pub enum Ipv6AddrGenMode {
    Eui64,
    // RFC 7217
    StablePrivacy,
    Other(String),
}

impl From<String> for Ipv6AddrGenMode {
    fn from(s: String) -> Self {
        return match s.as_str() {
            "eui64" | "EUI64" => Self::Eui64,
            "stable-privacy" | "STABLE-PRIVACY" => Self::StablePrivacy,
            _ => Self::Other(s),
        };
    }
}

impl From<Ipv6AddrGenMode> for String {
    fn from(v: Ipv6AddrGenMode) -> Self {
        match v {
            Ipv6AddrGenMode::Eui64 => "eui64".to_string(),
            Ipv6AddrGenMode::StablePrivacy => "stable-privacy".to_string(),
            Ipv6AddrGenMode::Other(s) => s,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub enum WaitIp {
    /// The activation is considered done once IPv4 stack or IPv6 stack is
    /// configure
    Any,
    /// The activation is considered done once IPv4 stack is configured.
    Ipv4,
    /// The activation is considered done once IPv6 stack is configured.
    Ipv6,
    /// The activation is considered done once both IPv4 and IPv6 stack are
    /// configured.
    #[serde(rename = "ipv4+ipv6")]
    Ipv4AndIpv6,
}

impl std::fmt::Display for WaitIp {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Any => "any",
                Self::Ipv4 => "ipv4",
                Self::Ipv6 => "ipv6",
                Self::Ipv4AndIpv6 => "ipv4+ipv6",
            }
        )
    }
}

pub(crate) fn validate_wait_ip(
    base_iface: &BaseInterface,
) -> Result<(), NmstateError> {
    if let Some(wait_ip) = base_iface.wait_ip.as_ref() {
        if (wait_ip == &WaitIp::Ipv4 || wait_ip == &WaitIp::Ipv4AndIpv6)
            && !base_iface
                .ipv4
                .as_ref()
                .map(|i| i.enabled)
                .unwrap_or_default()
        {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Cannot set 'wait-ip: {}' with IPv4 disabled. \
                    Interface: {}({})",
                    wait_ip, &base_iface.name, &base_iface.iface_type
                ),
            );
            log::error!("{}", e);
            return Err(e);
        }
        if (wait_ip == &WaitIp::Ipv6 || wait_ip == &WaitIp::Ipv4AndIpv6)
            && !base_iface
                .ipv6
                .as_ref()
                .map(|i| i.enabled)
                .unwrap_or_default()
        {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Cannot set 'wait-ip: {}' with IPv6 disabled. \
                    Interface: {}({})",
                    wait_ip, &base_iface.name, &base_iface.iface_type
                ),
            );
            log::error!("{}", e);
            return Err(e);
        }
    }
    Ok(())
}

pub(crate) fn merge_ip_stack(
    chg_net_state: &mut Interfaces,
    current: &Interfaces,
) {
    for (iface_name, iface) in chg_net_state.kernel_ifaces.iter_mut() {
        let cur_iface = if let Some(c) = current.kernel_ifaces.get(iface_name) {
            c
        } else {
            continue;
        };
        if !iface.base_iface().can_have_ip() {
            continue;
        }
        if let Some(cur_ip_conf) = cur_iface.base_iface().ipv4.as_ref() {
            if let Some(ip_conf) = iface.base_iface_mut().ipv4.as_mut() {
                if !ip_conf.prop_list.contains(&"enabled") {
                    ip_conf.enabled = cur_ip_conf.enabled;
                }
                if ip_conf.dhcp.is_none() && ip_conf.enabled {
                    ip_conf.dhcp = cur_ip_conf.dhcp;
                }
            }
        }
        if let Some(cur_ip_conf) = cur_iface.base_iface().ipv6.as_ref() {
            if let Some(ip_conf) = iface.base_iface_mut().ipv6.as_mut() {
                if !ip_conf.prop_list.contains(&"enabled") {
                    ip_conf.enabled = cur_ip_conf.enabled;
                }
                if ip_conf.dhcp.is_none() && ip_conf.enabled {
                    ip_conf.dhcp = cur_ip_conf.dhcp;
                }
                if ip_conf.autoconf.is_none() && ip_conf.enabled {
                    ip_conf.autoconf = cur_ip_conf.autoconf;
                }
            }
        }
    }
}

fn get_ip_prop_list(
    map: &serde_json::Map<String, serde_json::Value>,
) -> Vec<&'static str> {
    let mut ret = Vec::new();

    if map.contains_key("enabled") {
        ret.push("enabled")
    }
    if map.contains_key("dhcp") {
        ret.push("dhcp")
    }
    if map.contains_key("autoconf") {
        ret.push("autoconf")
    }
    if map.contains_key("dhcp-client-id") {
        ret.push("dhcp_client_id")
    }
    if map.contains_key("dhcp-duid") {
        ret.push("dhcp_duid")
    }
    if map.contains_key("address") {
        ret.push("addresses")
    }
    if map.contains_key("auto-dns") {
        ret.push("auto_dns")
    }
    if map.contains_key("auto-gateway") {
        ret.push("auto_gateway")
    }
    if map.contains_key("auto-routes") {
        ret.push("auto_routes")
    }
    if map.contains_key("auto-route-table-id") {
        ret.push("auto_table_id")
    }
    if map.contains_key("addr-gen-mode") {
        ret.push("addr_gen_mode")
    }
    ret
}
