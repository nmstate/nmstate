// SPDX-License-Identifier: Apache-2.0

use std::net::{Ipv4Addr, Ipv6Addr};
use std::str::FromStr;

use serde::{Deserialize, Serialize};

use crate::{
    ip::is_ipv6_addr, ErrorKind, MergedInterface, MergedNetworkState,
    NmstateError,
};

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
/// DNS resolver state. Example partial yaml output of [NetworkState] with
/// static DNS config:
/// ```yaml
/// ---
/// dns-resolver:
///   running:
///      server:
///      - 2001:db8:1::250
///      - 192.0.2.250
///      search:
///      - example.org
///      - example.net
///   config:
///      search:
///      - example.org
///      - example.net
///      server:
///      - 2001:db8:1::250
///      - 192.0.2.250
/// ```
pub struct DnsState {
    #[serde(skip_serializing_if = "Option::is_none")]
    /// The running effective state. The DNS server might be from DHCP(IPv6
    /// autoconf) or manual setup.
    /// Ignored when applying state.
    pub running: Option<DnsClientState>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// The static saved DNS resolver config.
    /// When applying, if this not mentioned(None), current static DNS config
    /// will be preserved as it was. If defined(Some), will override current
    /// static DNS config.
    pub config: Option<DnsClientState>,
}

impl DnsState {
    /// [DnsState] with empty static DNS resolver config.
    pub fn new() -> Self {
        Self::default()
    }

    pub fn is_empty(&self) -> bool {
        self.running.is_none() && self.config.is_none()
    }

    pub(crate) fn sanitize(&mut self) -> Result<(), NmstateError> {
        if let Some(config) = self.config.as_mut() {
            config.sanitize()?;
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
/// DNS Client state
pub struct DnsClientState {
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Name server IP address list.
    /// To remove all existing servers, please use `Some(Vec::new())`.
    /// If undefined(set to `None`), will preserve current config.
    pub server: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Search list for host-name lookup.
    /// To remove all existing search, please use `Some(Vec::new())`.
    /// If undefined(set to `None`), will preserve current config.
    pub search: Option<Vec<String>>,
    #[serde(skip)]
    // Lower is better
    pub(crate) priority: Option<i32>,
}

impl DnsClientState {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn is_empty(&self) -> bool {
        self.server.is_none() && self.search.is_none()
    }

    // Whether user want to purge all DNS settings
    pub(crate) fn is_purge(&self) -> bool {
        match (&self.server, &self.search) {
            (Some(srvs), Some(schs)) => srvs.is_empty() && schs.is_empty(),
            (Some(srvs), None) => srvs.is_empty(),
            (None, Some(schs)) => schs.is_empty(),
            (None, None) => true,
        }
    }

    pub(crate) fn is_null(&self) -> bool {
        self.server.as_ref().map(|s| s.len()).unwrap_or_default() == 0
            && self.search.as_ref().map(|s| s.len()).unwrap_or_default() == 0
    }

    // sanitize the IP addresses.
    pub(crate) fn sanitize(&mut self) -> Result<(), NmstateError> {
        if let Some(srvs) = self.server.as_mut() {
            let mut sanitized_srvs = Vec::new();
            for srv in srvs {
                if is_ipv6_addr(srv.as_str()) {
                    let splits: Vec<&str> = srv.split('%').collect();
                    if splits.len() == 2 {
                        if let Ok(ip_addr) = splits[0].parse::<Ipv6Addr>() {
                            sanitized_srvs
                                .push(format!("{}%{}", ip_addr, splits[1]));
                        }
                    } else if let Ok(ip_addr) = srv.parse::<Ipv6Addr>() {
                        sanitized_srvs.push(ip_addr.to_string());
                    } else {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!("Invalid DNS server string {srv}",),
                        ));
                    }
                } else if let Ok(ip_addr) = srv.parse::<Ipv4Addr>() {
                    sanitized_srvs.push(ip_addr.to_string());
                } else {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!("Invalid DNS server string {srv}",),
                    ));
                }
            }
            self.server = Some(sanitized_srvs);
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MergedDnsState {
    desired: DnsState,
    current: DnsState,
    pub(crate) servers: Vec<String>,
    pub(crate) searches: Vec<String>,
}

impl MergedDnsState {
    pub(crate) fn new(
        mut desired: DnsState,
        mut current: DnsState,
    ) -> Result<Self, NmstateError> {
        desired.sanitize()?;
        current.sanitize().ok();
        let mut servers = current
            .config
            .as_ref()
            .and_then(|c| c.server.clone())
            .unwrap_or_default();
        let mut searches = current
            .config
            .as_ref()
            .and_then(|c| c.search.clone())
            .unwrap_or_default();

        if let Some(conf) = desired.config.as_ref() {
            if conf.is_purge() {
                servers.clear();
                searches.clear();
            } else {
                if let Some(des_srvs) = conf.server.as_ref() {
                    servers.clear();
                    servers.extend_from_slice(des_srvs);
                }
                if let Some(des_schs) = conf.search.as_ref() {
                    searches.clear();
                    searches.extend_from_slice(des_schs);
                }
            }
        }

        Ok(Self {
            desired,
            current,
            servers,
            searches,
        })
    }

    pub(crate) fn is_changed(&self) -> bool {
        let cur_servers = self
            .current
            .config
            .as_ref()
            .and_then(|c| c.server.clone())
            .unwrap_or_default();
        let cur_searches = self
            .current
            .config
            .as_ref()
            .and_then(|c| c.search.clone())
            .unwrap_or_default();

        self.servers != cur_servers || self.searches != cur_searches
    }
}

impl MergedNetworkState {
    // * Specified interface is valid for hold IPv6 DNS config.
    // * Cannot have more than one IPv6 link-local DNS interface.
    pub(crate) fn validate_ipv6_link_local_address_dns_srv(
        &self,
    ) -> Result<(), NmstateError> {
        let mut iface_names = Vec::new();
        for srv in self.dns.servers.as_slice() {
            if let Some((_, iface_name)) = parse_dns_ipv6_link_local_srv(srv)? {
                let iface = if let Some(iface) =
                    self.interfaces.kernel_ifaces.get(iface_name)
                {
                    iface
                } else {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Desired IPv6 link local DNS server {srv} is \
                        pointing to interface {iface_name} \
                        which does not exist."
                        ),
                    ));
                };
                if iface.is_iface_valid_for_dns(true) {
                    iface_names.push(iface.merged.name());
                } else {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Interface {iface_name} has IPv6 disabled, \
                            hence cannot hold desired IPv6 link local \
                            DNS server {srv}"
                        ),
                    ));
                }
            }
        }
        if iface_names.len() >= 2 {
            return Err(NmstateError::new(
                ErrorKind::NotImplementedError,
                format!(
                    "Only support IPv6 link local DNS name server(s) \
                pointing to a single interface, but got '{}'",
                    iface_names.join(" ")
                ),
            ));
        }

        Ok(())
    }
}

pub(crate) fn parse_dns_ipv6_link_local_srv(
    srv: &str,
) -> Result<Option<(std::net::Ipv6Addr, &str)>, NmstateError> {
    if srv.contains('%') {
        let splits: Vec<&str> = srv.split('%').collect();
        if splits.len() == 2 {
            match std::net::Ipv6Addr::from_str(splits[0]) {
                Ok(ip) => return Ok(Some((ip, splits[1]))),
                Err(_) => {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Invalid IPv6 address in {srv}, only IPv6 link local \
                            address is allowed to have '%' character in DNS \
                            name server, the correct format should be \
                            'fe80::deef:1%eth1'"
                        ),
                    ));
                }
            }
        } else {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Invalid DNS server {srv}, the IPv6 \
                        link local DNS server should be in the format like \
                        'fe80::deef:1%eth1'"
                ),
            ));
        }
    }
    Ok(None)
}

impl MergedInterface {
    // IP stack is merged with current at this point.
    pub(crate) fn is_iface_valid_for_dns(&self, is_ipv6: bool) -> bool {
        if is_ipv6 {
            self.merged.base_iface().ipv6.as_ref().map(|ip_conf| {
                ip_conf.enabled
                    && (ip_conf.is_static()
                        || (ip_conf.is_auto()
                            && ip_conf.auto_dns == Some(false)))
            }) == Some(true)
        } else {
            self.merged.base_iface().ipv4.as_ref().map(|ip_conf| {
                ip_conf.enabled
                    && (ip_conf.is_static()
                        || (ip_conf.is_auto()
                            && ip_conf.auto_dns == Some(false)))
            }) == Some(true)
        }
    }
}
