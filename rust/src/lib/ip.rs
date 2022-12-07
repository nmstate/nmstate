use std::fmt;
use std::str::FromStr;

use log::{debug, warn};
use serde::de::{self, Deserializer, MapAccess, Visitor};
use serde::{ser::SerializeStruct, Deserialize, Serialize, Serializer};

use crate::{DnsClientState, ErrorKind, Interfaces, NmstateError};

#[derive(Debug, Clone, PartialEq, Default)]
#[non_exhaustive]
pub struct InterfaceIpv4 {
    pub enabled: bool,
    pub prop_list: Vec<&'static str>,
    pub dhcp: bool,
    pub addresses: Vec<InterfaceIpAddr>,
    pub(crate) dns: Option<DnsClientState>,
    pub auto_dns: Option<bool>,
    pub auto_gateway: Option<bool>,
    pub auto_routes: Option<bool>,
    pub auto_table_id: Option<u32>,
}

impl Serialize for InterfaceIpv4 {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut serial_struct = serializer.serialize_struct(
            "ipv4",
            if self.enabled {
                if self.dhcp {
                    self.prop_list.len()
                } else {
                    std::cmp::min(3, self.prop_list.len())
                }
            } else {
                1
            },
        )?;
        serial_struct.serialize_field("enabled", &self.enabled)?;
        if self.enabled {
            if self.prop_list.contains(&"dhcp") {
                serial_struct.serialize_field("dhcp", &self.dhcp)?;
            }
            if self.dhcp {
                if self.prop_list.contains(&"auto_dns") {
                    serial_struct
                        .serialize_field("auto-dns", &self.auto_dns)?;
                }
                if self.prop_list.contains(&"auto_gateway") {
                    serial_struct
                        .serialize_field("auto-gateway", &self.auto_gateway)?;
                }
                if self.prop_list.contains(&"auto_routes") {
                    serial_struct
                        .serialize_field("auto-routes", &self.auto_routes)?;
                }
                if self.prop_list.contains(&"auto_table_id") {
                    serial_struct.serialize_field(
                        "auto-route-table-id",
                        &self.auto_table_id,
                    )?;
                }
            }
            if self.prop_list.contains(&"addresses") {
                serial_struct.serialize_field("address", &self.addresses)?;
            }
        }
        serial_struct.end()
    }
}

impl<'de> Deserialize<'de> for InterfaceIpv4 {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        enum Field {
            Enabled,
            Dhcp,
            Address,
            AutoDns,
            AutoGateway,
            AutoRoutes,
            AutoRouteTableId,
        }

        impl<'de> Deserialize<'de> for Field {
            fn deserialize<D>(deserializer: D) -> Result<Field, D::Error>
            where
                D: Deserializer<'de>,
            {
                struct FieldVisitor;

                impl<'de> Visitor<'de> for FieldVisitor {
                    type Value = Field;

                    fn expecting(
                        &self,
                        formatter: &mut fmt::Formatter,
                    ) -> fmt::Result {
                        formatter.write_str(
                            "`enabled`, `dhcp`, `address`\
                            `auto-dns`, `auto-gateway`, `auto-routes` or \
                            `auto-route-table-id`",
                        )
                    }

                    fn visit_str<E>(self, value: &str) -> Result<Field, E>
                    where
                        E: de::Error,
                    {
                        match value {
                            "enabled" => Ok(Field::Enabled),
                            "dhcp" => Ok(Field::Dhcp),
                            "address" => Ok(Field::Address),
                            "auto-dns" => Ok(Field::AutoDns),
                            "auto-gateway" => Ok(Field::AutoGateway),
                            "auto-routes" => Ok(Field::AutoRoutes),
                            "auto-route-table-id" => {
                                Ok(Field::AutoRouteTableId)
                            }
                            _ => Err(de::Error::unknown_field(value, FIELDS)),
                        }
                    }
                }
                deserializer.deserialize_identifier(FieldVisitor)
            }
        }

        struct InterfaceIpv4Visitor;

        impl<'de> Visitor<'de> for InterfaceIpv4Visitor {
            type Value = InterfaceIpv4;

            fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
                formatter.write_str("struct InterfaceIpv4")
            }

            fn visit_map<V>(self, mut map: V) -> Result<InterfaceIpv4, V::Error>
            where
                V: MapAccess<'de>,
            {
                let mut enabled = false;
                let mut dhcp = false;
                let mut prop_list: Vec<&'static str> = Vec::new();
                let mut addresses: Vec<InterfaceIpAddr> = Vec::new();
                let mut auto_dns = None;
                let mut auto_routes = None;
                let mut auto_gateway = None;
                let mut auto_table_id = None;

                while let Some(key) = map.next_key()? {
                    match key {
                        Field::Enabled => {
                            if prop_list.contains(&"enabled") {
                                return Err(de::Error::duplicate_field(
                                    "enabled",
                                ));
                            }
                            enabled = map.next_value()?;
                            prop_list.push("enabled");
                        }
                        Field::Dhcp => {
                            if prop_list.contains(&"dhcp") {
                                return Err(de::Error::duplicate_field("dhcp"));
                            }
                            dhcp = map.next_value()?;
                            prop_list.push("dhcp");
                        }
                        Field::Address => {
                            if prop_list.contains(&"addresses") {
                                return Err(de::Error::duplicate_field(
                                    "address",
                                ));
                            }
                            addresses = map.next_value()?;
                            prop_list.push("addresses");
                        }
                        Field::AutoDns => {
                            if prop_list.contains(&"auto_dns") {
                                return Err(de::Error::duplicate_field(
                                    "address",
                                ));
                            }
                            auto_dns = map.next_value()?;
                            prop_list.push("auto_dns");
                        }
                        Field::AutoGateway => {
                            if prop_list.contains(&"auto_gateway") {
                                return Err(de::Error::duplicate_field(
                                    "address",
                                ));
                            }
                            auto_gateway = map.next_value()?;
                            prop_list.push("auto_gateway");
                        }
                        Field::AutoRoutes => {
                            if prop_list.contains(&"auto_routes") {
                                return Err(de::Error::duplicate_field(
                                    "address",
                                ));
                            }
                            auto_routes = map.next_value()?;
                            prop_list.push("auto_routes");
                        }
                        Field::AutoRouteTableId => {
                            if prop_list.contains(&"auto_table_id") {
                                return Err(de::Error::duplicate_field(
                                    "address",
                                ));
                            }
                            auto_table_id = map.next_value()?;
                            prop_list.push("auto_table_id");
                        }
                    }
                }
                Ok(InterfaceIpv4 {
                    enabled,
                    prop_list,
                    dhcp,
                    addresses,
                    auto_dns,
                    auto_gateway,
                    auto_routes,
                    auto_table_id,
                    dns: None,
                })
            }
        }
        const FIELDS: &[&str] = &[
            "enabled",
            "dhcp",
            "address",
            "auto-dns",
            "auto-gateway",
            "auto-routes",
            "auto-route-table-id",
        ];
        deserializer.deserialize_struct(
            "InterfaceIpv4",
            FIELDS,
            InterfaceIpv4Visitor,
        )
    }
}

impl InterfaceIpv4 {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn update(&mut self, other: &Self) {
        if other.prop_list.contains(&"enabled") {
            self.enabled = other.enabled;
        }
        if other.prop_list.contains(&"dhcp") {
            self.dhcp = other.dhcp;
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
    }

    // Clean up before sending to plugin for applying
    // * Convert expanded IP address to compacted
    // * Set auto_dns, auto_gateway and auto_routes to true if DHCP enabled and
    //   those options is None
    // * Remove static IP address when DHCP enabled.
    pub(crate) fn pre_edit_cleanup(&mut self) -> Result<(), NmstateError> {
        for addr in &mut self.addresses {
            addr.sanitize()?;
        }
        if self.enabled && self.dhcp {
            if self.auto_dns.is_none() {
                self.auto_dns = Some(true);
            }
            if self.auto_routes.is_none() {
                self.auto_routes = Some(true);
            }
            if self.auto_gateway.is_none() {
                self.auto_gateway = Some(true);
            }
            if !self.addresses.is_empty() {
                log::warn!(
                    "Static addresses {:?} are ignored when dynamic \
                    IP is enabled",
                    self.addresses.as_slice()
                );
                self.addresses = Vec::new();
            }
        }
        Ok(())
    }

    // Clean up before verification
    // * Sort IP address
    // * Convert expanded IP address to compacted
    // * Add optional properties to prop_list
    // * Ignore DHCP options if DHCP disabled
    // * Ignore address if DHCP enabled
    // * Set DHCP as off if enabled and dhcp is None
    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.addresses.sort_unstable_by(|a, b| {
            (&a.ip, a.prefix_length).cmp(&(&b.ip, b.prefix_length))
        });
        for addr in &mut self.addresses {
            if let Err(e) = addr.sanitize() {
                warn!("BUG: IP address sanitize failure: {}", e);
            }
        }
        debug!("IPv4 after pre_verify_cleanup: {:?}", self);
        self.prop_list.push("dhcp");
        if !self.enabled || !self.dhcp {
            self.prop_list.retain(|p| {
                !["auto_dns", "auto_routes", "auto_gateway", "auto_table_id"]
                    .contains(p)
            });
        }
        if self.enabled && self.dhcp && self.prop_list.contains(&"addresses") {
            self.prop_list.retain(|p| p != &"addresses")
        }
    }
}

#[derive(Debug, Clone, PartialEq, Default)]
#[non_exhaustive]
pub struct InterfaceIpv6 {
    pub enabled: bool,
    pub prop_list: Vec<&'static str>,
    pub dhcp: bool,
    pub autoconf: bool,
    pub addresses: Vec<InterfaceIpAddr>,
    pub(crate) dns: Option<DnsClientState>,
    pub auto_dns: Option<bool>,
    pub auto_gateway: Option<bool>,
    pub auto_routes: Option<bool>,
    pub auto_table_id: Option<u32>,
}

impl Serialize for InterfaceIpv6 {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut serial_struct = serializer.serialize_struct(
            "ipv6",
            if self.enabled {
                if self.dhcp || self.autoconf {
                    self.prop_list.len()
                } else {
                    // If DHCP disabled, we can only show
                    std::cmp::min(4, self.prop_list.len())
                }
            } else {
                1
            },
        )?;
        serial_struct.serialize_field("enabled", &self.enabled)?;
        if self.enabled {
            if self.prop_list.contains(&"dhcp") {
                serial_struct.serialize_field("dhcp", &self.dhcp)?;
            }
            if self.prop_list.contains(&"autoconf") {
                serial_struct.serialize_field("autoconf", &self.autoconf)?;
            }
            if self.dhcp || self.autoconf {
                if self.prop_list.contains(&"auto_dns") {
                    serial_struct
                        .serialize_field("auto-dns", &self.auto_dns)?;
                }
                if self.prop_list.contains(&"auto_gateway") {
                    serial_struct
                        .serialize_field("auto-gateway", &self.auto_gateway)?;
                }
                if self.prop_list.contains(&"auto_routes") {
                    serial_struct
                        .serialize_field("auto-routes", &self.auto_routes)?;
                }
                if self.prop_list.contains(&"auto_table_id") {
                    serial_struct.serialize_field(
                        "auto-route-table-id",
                        &self.auto_table_id,
                    )?;
                }
            }
            if self.prop_list.contains(&"addresses") {
                serial_struct.serialize_field("address", &self.addresses)?;
            }
        }
        serial_struct.end()
    }
}

impl<'de> Deserialize<'de> for InterfaceIpv6 {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        enum Field {
            Enabled,
            Dhcp,
            Autoconf,
            Address,
            AutoDns,
            AutoGateway,
            AutoRoutes,
            AutoRouteTableId,
        }

        impl<'de> Deserialize<'de> for Field {
            fn deserialize<D>(deserializer: D) -> Result<Field, D::Error>
            where
                D: Deserializer<'de>,
            {
                struct FieldVisitor;

                impl<'de> Visitor<'de> for FieldVisitor {
                    type Value = Field;

                    fn expecting(
                        &self,
                        formatter: &mut fmt::Formatter,
                    ) -> fmt::Result {
                        formatter.write_str(
                            "`enabled`, `dhcp`, `autoconf`, `address` \
                            `auto-dns`, `auto-gateway`, `auto-routes` or \
                            `auto-route-table-id`",
                        )
                    }

                    fn visit_str<E>(self, value: &str) -> Result<Field, E>
                    where
                        E: de::Error,
                    {
                        match value {
                            "enabled" => Ok(Field::Enabled),
                            "dhcp" => Ok(Field::Dhcp),
                            "autoconf" => Ok(Field::Autoconf),
                            "address" => Ok(Field::Address),
                            "auto-dns" => Ok(Field::AutoDns),
                            "auto-gateway" => Ok(Field::AutoGateway),
                            "auto-routes" => Ok(Field::AutoRoutes),
                            "auto-route-table-id" => {
                                Ok(Field::AutoRouteTableId)
                            }
                            _ => Err(de::Error::unknown_field(value, FIELDS)),
                        }
                    }
                }
                deserializer.deserialize_identifier(FieldVisitor)
            }
        }

        struct InterfaceIpv6Visitor;

        impl<'de> Visitor<'de> for InterfaceIpv6Visitor {
            type Value = InterfaceIpv6;

            fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
                formatter.write_str("struct InterfaceIpv6")
            }

            fn visit_map<V>(self, mut map: V) -> Result<InterfaceIpv6, V::Error>
            where
                V: MapAccess<'de>,
            {
                let mut enabled = false;
                let mut dhcp = false;
                let mut autoconf = false;
                let mut prop_list: Vec<&'static str> = Vec::new();
                let mut addresses: Vec<InterfaceIpAddr> = Vec::new();
                let mut auto_dns = None;
                let mut auto_routes = None;
                let mut auto_gateway = None;
                let mut auto_table_id = None;

                while let Some(key) = map.next_key()? {
                    match key {
                        Field::Enabled => {
                            if prop_list.contains(&"enabled") {
                                return Err(de::Error::duplicate_field(
                                    "enabled",
                                ));
                            }
                            enabled = map.next_value()?;
                            prop_list.push("enabled");
                        }
                        Field::Dhcp => {
                            if prop_list.contains(&"dhcp") {
                                return Err(de::Error::duplicate_field("dhcp"));
                            }
                            dhcp = map.next_value()?;
                            prop_list.push("dhcp");
                        }
                        Field::Autoconf => {
                            if prop_list.contains(&"autoconf") {
                                return Err(de::Error::duplicate_field(
                                    "autoconf",
                                ));
                            }
                            autoconf = map.next_value()?;
                            prop_list.push("autoconf");
                        }
                        Field::Address => {
                            if prop_list.contains(&"addresses") {
                                return Err(de::Error::duplicate_field(
                                    "address",
                                ));
                            }
                            addresses = map.next_value()?;
                            prop_list.push("addresses");
                        }
                        Field::AutoDns => {
                            if prop_list.contains(&"auto_dns") {
                                return Err(de::Error::duplicate_field(
                                    "address",
                                ));
                            }
                            auto_dns = map.next_value()?;
                            prop_list.push("auto_dns");
                        }
                        Field::AutoGateway => {
                            if prop_list.contains(&"auto_gateway") {
                                return Err(de::Error::duplicate_field(
                                    "address",
                                ));
                            }
                            auto_gateway = map.next_value()?;
                            prop_list.push("auto_gateway");
                        }
                        Field::AutoRoutes => {
                            if prop_list.contains(&"auto_routes") {
                                return Err(de::Error::duplicate_field(
                                    "address",
                                ));
                            }
                            auto_routes = map.next_value()?;
                            prop_list.push("auto_routes");
                        }
                        Field::AutoRouteTableId => {
                            if prop_list.contains(&"auto_table_id") {
                                return Err(de::Error::duplicate_field(
                                    "address",
                                ));
                            }
                            auto_table_id = map.next_value()?;
                            prop_list.push("auto_table_id");
                        }
                    }
                }
                Ok(InterfaceIpv6 {
                    enabled,
                    prop_list,
                    dhcp,
                    autoconf,
                    addresses,
                    auto_dns,
                    auto_gateway,
                    auto_routes,
                    auto_table_id,
                    dns: None,
                })
            }
        }
        const FIELDS: &[&str] = &[
            "enabled",
            "dhcp",
            "autoconf",
            "address",
            "auto-dns",
            "auto-gateway",
            "auto-routes",
            "auto-route-table-id",
        ];
        deserializer.deserialize_struct(
            "InterfaceIpv6",
            FIELDS,
            InterfaceIpv6Visitor,
        )
    }
}

impl InterfaceIpv6 {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn update(&mut self, other: &Self) {
        if other.prop_list.contains(&"enabled") {
            self.enabled = other.enabled;
        }
        if other.prop_list.contains(&"dhcp") {
            self.dhcp = other.dhcp;
        }
        if other.prop_list.contains(&"autoconf") {
            self.autoconf = other.autoconf;
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
        for other_prop_name in &other.prop_list {
            if !self.prop_list.contains(other_prop_name) {
                self.prop_list.push(other_prop_name);
            }
        }
    }

    // Clean up before verification
    // * Remove link-local address
    // * Sanitize the expanded IP address
    // * Add optional properties to prop_list
    // * Ignore DHCP options if DHCP disabled
    // * Ignore IP address when DHCP/autoconf enabled.
    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.addresses.retain(|addr| {
            !is_ipv6_unicast_link_local(&addr.ip, addr.prefix_length)
        });
        self.addresses.sort_unstable_by(|a, b| {
            (&a.ip, a.prefix_length).cmp(&(&b.ip, b.prefix_length))
        });
        for addr in &mut self.addresses {
            if let Err(e) = addr.sanitize() {
                warn!("BUG: IP address sanitize failure: {}", e);
            }
        }
        self.prop_list.push("dhcp");
        self.prop_list.push("autoconf");
        if !self.enabled || (!self.dhcp && !self.autoconf) {
            self.prop_list.retain(|p| {
                !["auto_dns", "auto_routes", "auto_gateway", "auto_table_id"]
                    .contains(p)
            });
        }
        if self.enabled
            && (self.dhcp || self.autoconf)
            && self.prop_list.contains(&"addresses")
        {
            self.prop_list.retain(|p| p != &"addresses")
        }
        debug!("IPv6 after pre_verify_cleanup: {:?}", self);
    }

    // Clean up before Apply
    // * Remove link-local address
    // * Sanitize the expanded IP address
    // * Set auto_dns, auto_gateway and auto_routes to true if DHCP/autoconf
    //   enabled and those options is None
    // * Remove static IP address when DHCP/autoconf enabled.
    pub(crate) fn pre_edit_cleanup(&mut self) -> Result<(), NmstateError> {
        self.addresses.retain(|addr| {
            if is_ipv6_unicast_link_local(&addr.ip, addr.prefix_length) {
                warn!(
                    "Ignoring IPv6 link local address {}/{}",
                    &addr.ip, addr.prefix_length
                );
                false
            } else {
                true
            }
        });
        for addr in &mut self.addresses {
            addr.sanitize()?;
        }
        if self.enabled && (self.dhcp || self.autoconf) {
            if self.auto_dns.is_none() {
                self.auto_dns = Some(true);
            }
            if self.auto_routes.is_none() {
                self.auto_routes = Some(true);
            }
            if self.auto_gateway.is_none() {
                self.auto_gateway = Some(true);
            }
            if !self.addresses.is_empty() {
                log::warn!(
                    "Static addresses {:?} are ignored when dynamic \
                    IP is enabled",
                    self.addresses.as_slice()
                );
                self.addresses = Vec::new();
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct InterfaceIpAddr {
    pub ip: String,
    pub prefix_length: u8,
}

impl InterfaceIpAddr {
    // TOOD: Check prefix_length also for 32 and 128 limitation.
    pub(crate) fn sanitize(&mut self) -> Result<(), NmstateError> {
        let ip = std::net::IpAddr::from_str(&self.ip)?;
        self.ip = ip.to_string();
        Ok(())
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
        let ip = addr[0].to_string();
        let prefix_length = if addr[1].is_empty() {
            if is_ipv6_addr(&ip) {
                128
            } else {
                32
            }
        } else {
            addr[1].parse::<u8>().map_err(|parse_error| {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!("Invalid IP address {value}: {parse_error}"),
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
            if cur_ip_conf.dhcp && !cur_ip_conf.addresses.is_empty() {
                if let Some(ip_conf) = iface.base_iface_mut().ipv4.as_mut() {
                    if ip_conf.enabled
                        && !ip_conf.dhcp
                        && !ip_conf.prop_list.contains(&"addresses")
                    {
                        ip_conf.addresses = cur_ip_conf.addresses.clone();
                        ip_conf.prop_list.push("addresses");
                    }
                }
            }
        }
        if let Some(cur_ip_conf) = cur_iface.base_iface().ipv6.as_ref() {
            if (cur_ip_conf.dhcp || cur_ip_conf.autoconf)
                && !cur_ip_conf.addresses.is_empty()
            {
                if let Some(ip_conf) = iface.base_iface_mut().ipv6.as_mut() {
                    if ip_conf.enabled
                        && !ip_conf.dhcp
                        && !ip_conf.autoconf
                        && !ip_conf.prop_list.contains(&"addresses")
                    {
                        ip_conf.addresses = cur_ip_conf.addresses.clone();
                        ip_conf.prop_list.push("addresses");
                    }
                }
            }
        }
    }
}
