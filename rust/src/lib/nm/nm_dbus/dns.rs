// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use super::{connection::_from_map, NmError};

#[derive(Debug, Clone, PartialEq, Default)]
pub struct NmDnsEntry {
    pub priority: i32,
    pub domains: Vec<String>,
    pub name_servers: Vec<String>,
    pub interface: String,
    pub is_vpn: bool,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<HashMap<String, zvariant::OwnedValue>> for NmDnsEntry {
    type Error = NmError;
    fn try_from(
        mut v: HashMap<String, zvariant::OwnedValue>,
    ) -> Result<Self, Self::Error> {
        Ok(Self {
            priority: _from_map!(v, "priority", i32::try_from)?
                .unwrap_or_default(),
            domains: _from_map!(v, "domains", Vec::<String>::try_from)?
                .unwrap_or_default(),
            name_servers: _from_map!(
                v,
                "nameservers",
                Vec::<String>::try_from
            )?
            .unwrap_or_default(),
            interface: _from_map!(v, "interface", String::try_from)?
                .unwrap_or_default(),
            is_vpn: _from_map!(v, "vpn", bool::try_from)?.unwrap_or_default(),
            _other: v,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Default)]
#[non_exhaustive]
pub struct NmGlobalDnsConfig {
    pub searches: Vec<String>,
    pub options: Vec<String>,
    pub domains: HashMap<String, NmGlobalDnsDomainConfig>,
}

impl NmGlobalDnsConfig {
    pub fn is_empty(&self) -> bool {
        self.searches.is_empty()
            && self.options.is_empty()
            && self.domains.is_empty()
    }

    pub fn new_wildcard(
        searches: Vec<String>,
        servers: Vec<String>,
        options: Vec<String>,
    ) -> Self {
        let mut domains = HashMap::new();
        domains.insert(
            "*".to_string(),
            NmGlobalDnsDomainConfig {
                servers,
                options: Vec::new(),
            },
        );
        Self {
            searches,
            domains,
            options,
        }
    }

    pub(crate) fn to_value(&self) -> Result<zvariant::Value, NmError> {
        let mut ret = zvariant::Dict::new(
            zvariant::Signature::from_str_unchecked("s"),
            zvariant::Signature::from_str_unchecked("v"),
        );
        if !self.searches.is_empty() {
            ret.append(
                zvariant::Value::new("searches"),
                zvariant::Value::new(zvariant::Value::new(
                    self.searches.clone(),
                )),
            )?;
        }
        if !self.options.is_empty() {
            ret.append(
                zvariant::Value::new("options"),
                zvariant::Value::new(zvariant::Value::new(
                    self.options.clone(),
                )),
            )?;
        }
        if !self.domains.is_empty() {
            ret.append(
                zvariant::Value::new("domains"),
                zvariant::Value::new(global_dns_domain_configs_to_value(
                    &self.domains,
                )?),
            )?;
        }
        Ok(zvariant::Value::Dict(ret))
    }
}

impl TryFrom<HashMap<String, zvariant::OwnedValue>> for NmGlobalDnsConfig {
    type Error = NmError;
    fn try_from(
        mut v: HashMap<String, zvariant::OwnedValue>,
    ) -> Result<Self, Self::Error> {
        Ok(Self {
            searches: _from_map!(v, "searches", Vec::<String>::try_from)?
                .unwrap_or_default(),
            options: _from_map!(v, "options", Vec::<String>::try_from)?
                .unwrap_or_default(),
            domains: _from_map!(v, "domains", parse_global_dns_domain_configs)?
                .unwrap_or_default(),
        })
    }
}

#[derive(Debug, Clone, PartialEq, Default)]
#[non_exhaustive]
pub struct NmGlobalDnsDomainConfig {
    pub servers: Vec<String>,
    pub options: Vec<String>,
}

impl NmGlobalDnsDomainConfig {
    pub(crate) fn to_value(&self) -> Result<zvariant::Value, NmError> {
        let mut ret = zvariant::Dict::new(
            zvariant::Signature::from_str_unchecked("s"),
            zvariant::Signature::from_str_unchecked("v"),
        );
        if !self.servers.is_empty() {
            ret.append(
                zvariant::Value::new("servers"),
                zvariant::Value::new(zvariant::Value::new(
                    self.servers.clone(),
                )),
            )?;
        }
        if !self.options.is_empty() {
            ret.append(
                zvariant::Value::new("options"),
                zvariant::Value::new(zvariant::Value::new(
                    self.options.clone(),
                )),
            )?;
        }
        Ok(zvariant::Value::Dict(ret))
    }
}

impl TryFrom<HashMap<String, zvariant::OwnedValue>>
    for NmGlobalDnsDomainConfig
{
    type Error = NmError;
    fn try_from(
        mut v: HashMap<String, zvariant::OwnedValue>,
    ) -> Result<Self, Self::Error> {
        Ok(Self {
            servers: _from_map!(v, "servers", Vec::<String>::try_from)?
                .unwrap_or_default(),
            options: _from_map!(v, "options", Vec::<String>::try_from)?
                .unwrap_or_default(),
        })
    }
}

fn parse_global_dns_domain_configs(
    v: zvariant::OwnedValue,
) -> Result<HashMap<String, NmGlobalDnsDomainConfig>, NmError> {
    let mut ret = HashMap::new();
    let mut raw_confs =
        HashMap::<String, HashMap<String, zvariant::OwnedValue>>::try_from(v)?;
    for (domain, raw_conf) in raw_confs.drain() {
        ret.insert(domain, NmGlobalDnsDomainConfig::try_from(raw_conf)?);
    }
    Ok(ret)
}

fn global_dns_domain_configs_to_value(
    configs: &HashMap<String, NmGlobalDnsDomainConfig>,
) -> Result<zvariant::Value, NmError> {
    let mut ret = zvariant::Dict::new(
        zvariant::Signature::from_str_unchecked("s"),
        zvariant::Signature::from_str_unchecked("v"),
    );
    for (domain, config) in configs.iter() {
        ret.append(
            zvariant::Value::new(domain.as_str()),
            zvariant::Value::new(config.to_value()?),
        )?;
    }
    Ok(zvariant::Value::Dict(ret))
}
