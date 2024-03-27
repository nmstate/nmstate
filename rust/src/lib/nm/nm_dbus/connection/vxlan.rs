// SPDX-License-Identifier: Apache-2.0
use std::collections::HashMap;
use std::convert::TryFrom;

use serde::Deserialize;

use super::super::{connection::DbusDictionary, NmError, ToDbusValue};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingVxlan {
    pub parent: Option<String>,
    pub id: Option<u32>,
    pub learning: Option<bool>,
    pub local: Option<String>,
    pub remote: Option<String>,
    pub dst_port: Option<u32>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingVxlan {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            parent: _from_map!(v, "parent", String::try_from)?,
            id: _from_map!(v, "id", u32::try_from)?,
            learning: _from_map!(v, "learning", bool::try_from)?,
            local: _from_map!(v, "local", String::try_from)?,
            remote: _from_map!(v, "remote", String::try_from)?,
            dst_port: _from_map!(v, "destination-port", u32::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingVxlan {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = self.parent.as_deref() {
            if !v.is_empty() {
                ret.insert("parent", zvariant::Value::new(v));
            }
        }
        if let Some(id) = self.id {
            ret.insert("id", zvariant::Value::new(id));
        }
        if let Some(v) = self.learning {
            ret.insert("learning", zvariant::Value::new(v));
        }
        if let Some(v) = &self.local {
            ret.insert("local", zvariant::Value::new(v));
        }
        if let Some(v) = &self.remote {
            ret.insert("remote", zvariant::Value::new(v));
        }
        if let Some(v) = self.dst_port {
            ret.insert("destination-port", zvariant::Value::new(v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}
