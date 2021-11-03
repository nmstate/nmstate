use std::fmt;
use std::str::FromStr;

use log::{debug, warn};
use serde::de::{self, Deserializer, MapAccess, Visitor};
use serde::{ser::SerializeStruct, Deserialize, Serialize, Serializer};

use crate::NmstateError;

#[derive(Debug, Clone, PartialEq, Default)]
pub struct InterfaceIpv4 {
    pub enabled: bool,
    pub prop_list: Vec<&'static str>,
    pub dhcp: bool,
    pub addresses: Vec<InterfaceIpAddr>,
}

impl Serialize for InterfaceIpv4 {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut serial_struct = serializer.serialize_struct(
            "ipv4",
            if self.enabled {
                self.prop_list.len()
            } else {
                1
            },
        )?;
        serial_struct.serialize_field("enabled", &self.enabled)?;
        if self.enabled {
            if self.prop_list.contains(&"dhcp") {
                serial_struct.serialize_field("dhcp", &self.dhcp)?;
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
                        formatter.write_str("`enabled`, `dhcp` or `address`")
                    }

                    fn visit_str<E>(self, value: &str) -> Result<Field, E>
                    where
                        E: de::Error,
                    {
                        match value {
                            "enabled" => Ok(Field::Enabled),
                            "dhcp" => Ok(Field::Dhcp),
                            "address" => Ok(Field::Address),
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
                    }
                }
                Ok(InterfaceIpv4 {
                    enabled,
                    prop_list,
                    dhcp,
                    addresses,
                })
            }
        }
        const FIELDS: &[&str] = &["enabled", "dhcp", "address"];
        deserializer.deserialize_struct(
            "InterfaceIpv4",
            FIELDS,
            InterfaceIpv4Visitor,
        )
    }
}

impl InterfaceIpv4 {
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
        for other_prop_name in &other.prop_list {
            if !self.prop_list.contains(other_prop_name) {
                self.prop_list.push(other_prop_name);
            }
        }
    }

    // Clean up before sending to plugin for applying
    // * Convert expanded IP address to compacted
    pub(crate) fn pre_edit_cleanup(&mut self) -> Result<(), NmstateError> {
        for addr in &mut self.addresses {
            addr.sanitize()?;
        }
        Ok(())
    }

    // Clean up before verification
    // * Sort IP address
    // * Convert expanded IP address to compacted
    // * Add optional properties to prop_list
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
    }
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct InterfaceIpv6 {
    pub enabled: bool,
    pub prop_list: Vec<&'static str>,
    pub dhcp: bool,
    pub autoconf: bool,
    pub addresses: Vec<InterfaceIpAddr>,
}

impl Serialize for InterfaceIpv6 {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut serial_struct = serializer.serialize_struct(
            "ipv6",
            if self.enabled {
                1
            } else {
                self.prop_list.len()
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
                            "`enabled`, `dhcp`, `autoconf` or `address`",
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
                    }
                }
                Ok(InterfaceIpv6 {
                    enabled,
                    prop_list,
                    dhcp,
                    autoconf,
                    addresses,
                })
            }
        }
        const FIELDS: &[&str] = &["enabled", "dhcp", "autoconf", "address"];
        deserializer.deserialize_struct(
            "InterfaceIpv6",
            FIELDS,
            InterfaceIpv6Visitor,
        )
    }
}

impl InterfaceIpv6 {
    pub(crate) fn update(&mut self, other: &Self) {
        if other.prop_list.contains(&"enabled") {
            self.enabled = other.enabled;
        }
        if other.prop_list.contains(&"dhcp") {
            self.dhcp = other.dhcp;
        }
        if other.prop_list.contains(&"autoconf") {
            self.dhcp = other.dhcp;
        }
        if other.prop_list.contains(&"addresses") {
            self.addresses = other.addresses.clone();
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
        debug!("IPv6 after pre_verify_cleanup: {:?}", self);
        self.prop_list.push("dhcp");
        self.prop_list.push("autoconf");
    }

    // Clean up before Apply
    // * Remove link-local address
    // * Sanitize the expanded IP address
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
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub struct InterfaceIpAddr {
    pub ip: String,
    pub prefix_length: u32,
}

impl InterfaceIpAddr {
    // TOOD: Check prefix_length also for 32 and 128 limitation.
    pub(crate) fn sanitize(&mut self) -> Result<(), NmstateError> {
        let ip = std::net::IpAddr::from_str(&self.ip)?;
        self.ip = ip.to_string();
        Ok(())
    }
}

fn is_ipv6_addr(addr: &str) -> bool {
    addr.contains(':')
}

// TODO: Rust offical has std::net::Ipv6Addr::is_unicast_link_local() in
// experimental.
fn is_ipv6_unicast_link_local(ip: &str, prefix: u32) -> bool {
    // The unicast link local address range is fe80::/10.
    is_ipv6_addr(ip)
        && ip.len() >= 3
        && ["fe8", "fe9", "fea", "feb"].contains(&&ip[..3])
        && prefix >= 10
}
