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
use std::fmt::Write;

use log::error;

use serde::Deserialize;

use crate::{
    connection::DbusDictionary, dbus_value::own_value_to_bytes_array,
    dbus_value::own_value_to_u32, error::NmError,
};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
pub struct NmSettingWired {
    pub cloned_mac_address: Option<String>,
    pub mtu: Option<u32>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingWired {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            cloned_mac_address: _from_map!(
                v,
                "cloned-mac-address",
                own_value_to_bytes_array
            )?
            .map(u8_array_to_mac_string),
            mtu: _from_map!(v, "mtu", own_value_to_u32)?,
            _other: v,
        })
    }
}

impl NmSettingWired {
    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.cloned_mac_address {
            ret.insert(
                "cloned-mac-address",
                zvariant::Value::new(mac_str_to_u8_array(v)),
            );
        }
        if let Some(v) = &self.mtu {
            ret.insert("mtu", zvariant::Value::new(v));
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

fn u8_array_to_mac_string(data: Vec<u8>) -> String {
    let mut mac_addr = String::new();
    for byte in &data {
        if let Err(e) = write!(&mut mac_addr, "{:02X}:", byte) {
            error!(
                "Failed to convert bytes array to MAC address {:?}: {}",
                data, e
            );
            return "".to_string();
        }
    }
    mac_addr.pop();
    mac_addr
}

fn mac_str_to_u8_array(mac: &str) -> Vec<u8> {
    let mut mac_bytes = Vec::new();
    for item in mac.split(':') {
        match u8::from_str_radix(item, 16) {
            Ok(i) => mac_bytes.push(i),
            Err(e) => {
                error!(
                    "Failed to convert to MAC address to bytes {:?}: {}",
                    mac, e
                );
                return Vec::new();
            }
        }
    }
    mac_bytes
}
