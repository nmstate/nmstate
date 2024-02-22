// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use serde::Deserialize;

use super::super::{connection::DbusDictionary, NmError, ToDbusValue};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingGeneric {
    pub device_handler: Option<String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingGeneric {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            device_handler: _from_map!(v, "device-handler", String::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingGeneric {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.device_handler {
            ret.insert("device-handler", zvariant::Value::new(v.clone()));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}
