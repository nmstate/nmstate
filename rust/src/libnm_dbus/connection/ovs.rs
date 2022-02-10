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

use serde::Deserialize;

use crate::{connection::DbusDictionary, error::NmError};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingOvsBridge {
    pub stp: Option<bool>,
    pub mcast_snooping_enable: Option<bool>,
    pub rstp: Option<bool>,
    pub fail_mode: Option<String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingOvsBridge {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            stp: _from_map!(v, "stp-enable", bool::try_from)?,
            mcast_snooping_enable: _from_map!(
                v,
                "mcast-snooping-enable",
                bool::try_from
            )?,
            rstp: _from_map!(v, "rstp-enable", bool::try_from)?,
            fail_mode: _from_map!(v, "fail-mode", String::try_from)?,
            _other: v,
        })
    }
}

impl NmSettingOvsBridge {
    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = self.stp {
            ret.insert("stp-enable", zvariant::Value::new(v));
        }
        if let Some(v) = self.mcast_snooping_enable {
            ret.insert("mcast-snooping-enable", zvariant::Value::new(v));
        }
        if let Some(v) = self.rstp {
            ret.insert("rstp-enable", zvariant::Value::new(v));
        }
        if let Some(v) = &self.fail_mode {
            ret.insert("fail-mode", zvariant::Value::new(v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }

    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingOvsPort {
    pub mode: Option<String>,
    pub up_delay: Option<u32>,
    pub down_delay: Option<u32>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingOvsPort {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            mode: _from_map!(v, "bond-mode", String::try_from)?,
            up_delay: _from_map!(v, "bond-updelay", u32::try_from)?,
            down_delay: _from_map!(v, "bond-downdelay", u32::try_from)?,
            _other: v,
        })
    }
}

impl NmSettingOvsPort {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.mode {
            ret.insert("bond-mode", zvariant::Value::new(v));
        }
        if let Some(v) = self.up_delay {
            ret.insert("bond-updelay", zvariant::Value::new(v));
        }
        if let Some(v) = self.down_delay {
            ret.insert("bond-downdelay", zvariant::Value::new(v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingOvsIface {
    pub iface_type: Option<String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingOvsIface {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            iface_type: _from_map!(v, "type", String::try_from)?,
            _other: v,
        })
    }
}

impl NmSettingOvsIface {
    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.iface_type {
            ret.insert("type", zvariant::Value::new(v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }

    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingOvsExtIds {
    pub data: Option<HashMap<String, String>>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingOvsExtIds {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            data: _from_map!(v, "data", <HashMap<String, String>>::try_from)?,
            _other: v,
        })
    }
}

impl NmSettingOvsExtIds {
    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.data {
            let mut dict_value = zvariant::Dict::new(
                zvariant::Signature::from_str_unchecked("s"),
                zvariant::Signature::from_str_unchecked("s"),
            );
            for (k, v) in v.iter() {
                dict_value
                    .append(zvariant::Value::new(k), zvariant::Value::new(v))?;
            }
            ret.insert("data", zvariant::Value::Dict(dict_value));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }

    pub fn new() -> Self {
        Self::default()
    }
}
