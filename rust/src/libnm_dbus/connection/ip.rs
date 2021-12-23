// Copyright 2021 Red Hat, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

use std::collections::HashMap;
use std::convert::TryFrom;

use log::warn;

use serde::Deserialize;

use crate::{
    connection::route::{
        nm_ip_routes_to_value, parse_nm_ip_route_data, NmIpRoute,
    },
    connection::DbusDictionary,
    error::{ErrorKind, NmError},
};

#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(try_from = "zvariant::OwnedValue")]
pub enum NmSettingIpMethod {
    Auto,
    Disabled,
    LinkLocal,
    Manual,
    Shared,
    Dhcp,   // IPv6 only,
    Ignore, // Ipv6 only,
}

impl Default for NmSettingIpMethod {
    fn default() -> Self {
        Self::Auto
    }
}

impl std::fmt::Display for NmSettingIpMethod {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Auto => "auto",
                Self::Disabled => "disabled",
                Self::LinkLocal => "link-local",
                Self::Manual => "manual",
                Self::Shared => "shared",
                Self::Dhcp => "dhcp",
                Self::Ignore => "ignore",
            }
        )
    }
}

impl TryFrom<zvariant::OwnedValue> for NmSettingIpMethod {
    type Error = NmError;
    fn try_from(value: zvariant::OwnedValue) -> Result<Self, Self::Error> {
        let str_value = String::try_from(value)?;
        match str_value.as_str() {
            "auto" => Ok(Self::Auto),
            "disabled" => Ok(Self::Disabled),
            "link-local" => Ok(Self::LinkLocal),
            "manual" => Ok(Self::Manual),
            "shared" => Ok(Self::Shared),
            "dhcp" => Ok(Self::Dhcp),
            "ignore" => Ok(Self::Ignore),
            _ => Err(NmError::new(
                ErrorKind::InvalidArgument,
                format!("Invalid IP method {}", str_value),
            )),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
pub struct NmSettingIp {
    pub method: Option<NmSettingIpMethod>,
    pub addresses: Vec<String>,
    pub routes: Vec<NmIpRoute>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingIp {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        let mut setting = Self::new();
        setting.method = _from_map!(v, "method", NmSettingIpMethod::try_from)?;
        setting.addresses =
            _from_map!(v, "address-data", parse_nm_ip_address_data)?
                .unwrap_or_default();
        setting.routes = _from_map!(v, "route-data", parse_nm_ip_route_data)?
            .unwrap_or_default();

        // NM deprecated `addresses` property in the favor of `addresss-data`
        v.remove("addresses");
        // NM deprecated `routes` property in the favor of `routes-data`
        v.remove("routes");
        setting._other = v;
        Ok(setting)
    }
}

impl NmSettingIp {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.method {
            ret.insert("method", zvariant::Value::new(format!("{}", v)));
        }
        let mut addresss_data = zvariant::Array::new(
            zvariant::Signature::from_str_unchecked("a{sv}"),
        );
        for addr_str in &self.addresses {
            let addr_str_split: Vec<&str> = addr_str.split('/').collect();
            if addr_str_split.len() != 2 {
                return Err(NmError::new(
                    ErrorKind::InvalidArgument,
                    format!("Invalid IP address {}", addr_str),
                ));
            }
            let prefix = addr_str_split[1].parse::<u32>().map_err(|e| {
                NmError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Invalid IP address prefix {}: {}",
                        addr_str_split[1], e
                    ),
                )
            })?;
            let mut addr_dict = zvariant::Dict::new(
                zvariant::Signature::from_str_unchecked("s"),
                zvariant::Signature::from_str_unchecked("v"),
            );
            addr_dict.append(
                zvariant::Value::new("address".to_string()),
                zvariant::Value::Value(Box::new(zvariant::Value::new(
                    addr_str_split[0].to_string(),
                ))),
            )?;
            addr_dict.append(
                zvariant::Value::new("prefix".to_string()),
                zvariant::Value::Value(Box::new(zvariant::Value::U32(prefix))),
            )?;
            addresss_data.append(zvariant::Value::Dict(addr_dict))?;
        }
        ret.insert("address-data", zvariant::Value::Array(addresss_data));
        ret.insert("route-data", nm_ip_routes_to_value(&self.routes)?);
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

fn parse_nm_ip_address_data(
    value: zvariant::OwnedValue,
) -> Result<Vec<String>, NmError> {
    let mut addresses = Vec::new();
    for nm_addr in <Vec<zvariant::OwnedValue>>::try_from(value)? {
        let nm_addr_display = format!("{:?}", nm_addr);
        let mut nm_addr =
            match <HashMap<String, zvariant::OwnedValue>>::try_from(nm_addr) {
                Ok(a) => a,
                Err(e) => {
                    warn!(
                        "Failed to convert {} to HashMap: {}",
                        nm_addr_display, e
                    );
                    continue;
                }
            };
        let address = if let Some(a) = nm_addr
            .remove("address")
            .and_then(|a| String::try_from(a).ok())
        {
            a
        } else {
            warn!("Failed to find address property from {:?}", nm_addr);

            continue;
        };
        let prefix = if let Some(a) =
            nm_addr.remove("prefix").and_then(|a| u32::try_from(a).ok())
        {
            a
        } else {
            warn!("Failed to find address property from {:?}", nm_addr);

            continue;
        };
        addresses.push(format!("{}/{}", address, prefix));
    }
    Ok(addresses)
}
