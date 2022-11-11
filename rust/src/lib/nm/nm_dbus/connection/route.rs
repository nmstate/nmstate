// SPDX-License-Identifier: Apache-2.0

use std::convert::TryFrom;

use serde::Deserialize;

use super::super::{connection::DbusDictionary, NmError};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmIpRoute {
    pub dest: Option<String>,
    pub prefix: Option<u32>,
    pub next_hop: Option<String>,
    pub table: Option<u32>,
    pub metric: Option<u32>,
    _other: DbusDictionary,
}

impl TryFrom<DbusDictionary> for NmIpRoute {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            dest: _from_map!(v, "dest", String::try_from)?,
            prefix: _from_map!(v, "prefix", u32::try_from)?,
            next_hop: _from_map!(v, "next-hop", String::try_from)?,
            table: _from_map!(v, "table", u32::try_from)?,
            metric: _from_map!(v, "metric", u32::try_from)?,
            _other: v,
        })
    }
}

impl NmIpRoute {
    fn to_value(&self) -> Result<zvariant::Value, NmError> {
        let mut ret = zvariant::Dict::new(
            zvariant::Signature::from_str_unchecked("s"),
            zvariant::Signature::from_str_unchecked("v"),
        );
        if let Some(v) = &self.dest {
            ret.append(
                zvariant::Value::new("dest"),
                zvariant::Value::new(zvariant::Value::new(v)),
            )?;
        }
        if let Some(v) = &self.prefix {
            ret.append(
                zvariant::Value::new("prefix"),
                zvariant::Value::new(zvariant::Value::new(v)),
            )?;
        }
        if let Some(v) = &self.next_hop {
            ret.append(
                zvariant::Value::new("next-hop"),
                zvariant::Value::new(zvariant::Value::new(v)),
            )?;
        }
        if let Some(v) = &self.table {
            ret.append(
                zvariant::Value::new("table"),
                zvariant::Value::new(zvariant::Value::new(v)),
            )?;
        }
        if let Some(v) = &self.metric {
            ret.append(
                zvariant::Value::new("metric"),
                zvariant::Value::new(zvariant::Value::new(v)),
            )?;
        }

        for (key, value) in self._other.iter() {
            ret.append(
                zvariant::Value::new(key.as_str()),
                zvariant::Value::from(value.clone()),
            )?;
        }
        Ok(zvariant::Value::Dict(ret))
    }
}

pub(crate) fn parse_nm_ip_route_data(
    value: zvariant::OwnedValue,
) -> Result<Vec<NmIpRoute>, NmError> {
    let mut routes = Vec::new();
    for nm_route_value in <Vec<DbusDictionary>>::try_from(value)? {
        routes.push(NmIpRoute::try_from(nm_route_value)?);
    }
    Ok(routes)
}

pub(crate) fn nm_ip_routes_to_value(
    nm_routes: &[NmIpRoute],
) -> Result<zvariant::Value, NmError> {
    let mut route_values =
        zvariant::Array::new(zvariant::Signature::from_str_unchecked("a{sv}"));
    for nm_route in nm_routes {
        route_values.append(nm_route.to_value()?)?;
    }
    Ok(zvariant::Value::Array(route_values))
}
