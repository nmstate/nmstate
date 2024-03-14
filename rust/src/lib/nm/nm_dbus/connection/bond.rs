// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use serde::Deserialize;
use zvariant::Value;

use super::super::{connection::DbusDictionary, NmError, ToDbusValue};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingBond {
    pub options: HashMap<String, String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingBond {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            options: _from_map!(
                v,
                "options",
                <HashMap<String, String>>::try_from
            )?
            .unwrap_or_default(),
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingBond {
    fn to_value(&self) -> Result<HashMap<&str, Value>, NmError> {
        let mut ret = HashMap::new();
        ret.insert("options", Value::from(self.options.clone()));
        ret.extend(
            self._other
                .iter()
                .map(|(key, value)| (key.as_str(), Value::from(value.clone()))),
        );
        Ok(ret)
    }
}

#[derive(Debug, Clone, PartialEq, Default)]
#[non_exhaustive]
pub struct NmSettingBondPort {
    pub priority: Option<i32>,
    pub queue_id: Option<u32>,
    _other: DbusDictionary,
}

impl TryFrom<DbusDictionary> for NmSettingBondPort {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            priority: _from_map!(v, "prio", i32::try_from)?,
            queue_id: _from_map!(v, "queue-id", u32::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingBondPort {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();

        self.priority
            .map(|v| ret.insert("prio", zvariant::Value::new(v)));
        self.queue_id
            .map(|v| ret.insert("queue-id", zvariant::Value::new(v)));

        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}
