use std::str::FromStr;

use log::{debug, warn};
use serde::{ser::SerializeStruct, Deserialize, Serialize, Serializer};

use crate::NmstateError;

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
pub struct InterfaceIpv4 {
    #[serde(default)]
    pub enabled: bool,
    #[serde(skip)]
    pub prop_list: Vec<&'static str>,
    #[serde(default)]
    pub dhcp: bool,
    #[serde(rename = "address", default)]
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
            if self.prop_list.contains(&"addresses") {
                serial_struct.serialize_field("address", &self.addresses)?;
            }
        }
        serial_struct.end()
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
    }
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
pub struct InterfaceIpv6 {
    #[serde(default)]
    pub enabled: bool,
    #[serde(skip)]
    pub prop_list: Vec<&'static str>,
    #[serde(default)]
    pub dhcp: bool,
    #[serde(default)]
    pub autoconf: bool,
    #[serde(rename = "address", default)]
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
