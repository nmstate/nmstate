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

use crate::{dbus_value::value_hash_get_bool, error::NmError};

#[derive(Debug, Clone, PartialEq, Default)]
pub struct NmSettingBridge {
    pub stp: Option<bool>,
}

impl TryFrom<&HashMap<String, zvariant::OwnedValue>> for NmSettingBridge {
    type Error = NmError;
    fn try_from(
        value: &HashMap<String, zvariant::OwnedValue>,
    ) -> Result<Self, Self::Error> {
        Ok(Self {
            stp: value_hash_get_bool(value, "stp")?,
        })
    }
}

impl NmSettingBridge {
    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = self.stp {
            ret.insert("stp", zvariant::Value::new(v));
        }
        Ok(ret)
    }
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct NmSettingBridgePort {
    // TODO: bridge port vlan filter.
}

impl TryFrom<&HashMap<String, zvariant::OwnedValue>> for NmSettingBridgePort {
    type Error = NmError;
    fn try_from(
        _value: &HashMap<String, zvariant::OwnedValue>,
    ) -> Result<Self, Self::Error> {
        Ok(Self {})
    }
}

impl NmSettingBridgePort {
    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        Ok(HashMap::new())
    }
}
