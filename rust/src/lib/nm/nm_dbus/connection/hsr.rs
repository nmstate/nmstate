// SPDX-License-Identifier: Apache-2.0

use std::{collections::HashMap, convert::TryFrom};

use serde::{Deserialize, Serialize};

use super::super::{NmError, ToDbusValue, connection::DbusDictionary};

#[derive(Debug, Clone, PartialEq, Default, Deserialize, Serialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingHsr {
    pub port1: Option<String>,
    pub port2: Option<String>,
    pub multicast_spec: Option<u32>,
    pub protocol_version: Option<i32>,
    pub prp: Option<bool>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingHsr {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            port1: _from_map!(v, "port1", String::try_from)?,
            port2: _from_map!(v, "port2", String::try_from)?,
            multicast_spec: _from_map!(v, "multicast-spec", u32::try_from)?,
            protocol_version: _from_map!(v, "protocol-version", i32::try_from)?,
            prp: _from_map!(v, "prp", bool::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingHsr {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value<'_>>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.port1 {
            ret.insert("port1", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.port2 {
            ret.insert("port2", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.multicast_spec
            && *v > 0
        {
            ret.insert("multicast-spec", zvariant::Value::new(*v));
        }
        if let Some(v) = &self.prp {
            ret.insert("prp", zvariant::Value::new(*v));
        }
        if let Some(v) = &self.protocol_version {
            ret.insert("protocol-version", zvariant::Value::new(*v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}
