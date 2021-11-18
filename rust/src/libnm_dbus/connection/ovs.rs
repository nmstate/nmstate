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

use crate::{
    dbus_value::{own_value_to_bool, own_value_to_string, own_value_to_u32},
    error::NmError,
};

#[derive(Debug, Clone, PartialEq, Default)]
pub struct NmSettingOvsBridge {
    pub stp: Option<bool>,
    pub mcast_snooping_enable: Option<bool>,
    pub rstp: Option<bool>,
    pub fail_mode: Option<String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<HashMap<String, zvariant::OwnedValue>> for NmSettingOvsBridge {
    type Error = NmError;
    fn try_from(
        mut setting_value: HashMap<String, zvariant::OwnedValue>,
    ) -> Result<Self, Self::Error> {
        let mut setting = Self::new();
        setting.stp = setting_value
            .remove("stp-enable")
            .map(own_value_to_bool)
            .transpose()?;
        setting.mcast_snooping_enable = setting_value
            .remove("mcast-snooping-enable")
            .map(own_value_to_bool)
            .transpose()?;
        setting.rstp = setting_value
            .remove("rstp-enable")
            .map(own_value_to_bool)
            .transpose()?;
        setting.fail_mode = setting_value
            .remove("fail-mode")
            .map(own_value_to_string)
            .transpose()?;
        setting._other = setting_value;
        Ok(setting)
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

#[derive(Debug, Clone, PartialEq, Default)]
pub struct NmSettingOvsPort {
    pub mode: Option<String>,
    pub up_delay: Option<u32>,
    pub down_delay: Option<u32>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<HashMap<String, zvariant::OwnedValue>> for NmSettingOvsPort {
    type Error = NmError;
    fn try_from(
        mut setting_value: HashMap<String, zvariant::OwnedValue>,
    ) -> Result<Self, Self::Error> {
        let mut setting = Self::new();
        setting.mode = setting_value
            .remove("bond-mode")
            .map(own_value_to_string)
            .transpose()?;
        setting.up_delay = setting_value
            .remove("bond-updelay")
            .map(own_value_to_u32)
            .transpose()?;
        setting.down_delay = setting_value
            .remove("bond-downdelay")
            .map(own_value_to_u32)
            .transpose()?;
        setting._other = setting_value;
        Ok(setting)
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

#[derive(Debug, Clone, PartialEq, Default)]
pub struct NmSettingOvsIface {
    pub iface_type: Option<String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<HashMap<String, zvariant::OwnedValue>> for NmSettingOvsIface {
    type Error = NmError;
    fn try_from(
        mut setting_value: HashMap<String, zvariant::OwnedValue>,
    ) -> Result<Self, Self::Error> {
        let mut setting = Self::new();
        setting.iface_type = setting_value
            .remove("type")
            .map(own_value_to_string)
            .transpose()?;
        setting._other = setting_value;
        Ok(setting)
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
