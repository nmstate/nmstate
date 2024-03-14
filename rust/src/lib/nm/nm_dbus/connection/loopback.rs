// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use serde::Deserialize;

use super::super::{connection::DbusDictionary, NmError, ToDbusValue};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingLoopback {
    pub mtu: Option<u32>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingLoopback {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            mtu: _from_map!(v, "mtu", u32::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingLoopback {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.mtu {
            ret.insert("mtu", zvariant::Value::new(v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}
