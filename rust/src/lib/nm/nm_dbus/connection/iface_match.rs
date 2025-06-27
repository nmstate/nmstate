// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use serde::{Deserialize, Serialize};

use super::super::{connection::DbusDictionary, NmError, ToDbusValue};

#[derive(Debug, Clone, PartialEq, Default, Deserialize, Serialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingMatch {
    pub interface_name: Option<Vec<String>>,
    pub driver: Option<Vec<String>>,
    pub path: Option<Vec<String>>,
    pub kernel_command_line: Option<Vec<String>>,
    pub(crate) _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingMatch {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            interface_name: _from_map!(
                v,
                "interface-name",
                Vec::<String>::try_from
            )?,
            driver: _from_map!(v, "driver", Vec::<String>::try_from)?,
            path: _from_map!(v, "path", Vec::<String>::try_from)?,
            kernel_command_line: _from_map!(
                v,
                "kernel-command-line",
                Vec::<String>::try_from
            )?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingMatch {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value<'_>>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.interface_name {
            ret.insert("interface-name", zvariant::Value::new(v));
        }
        if let Some(v) = &self.driver {
            ret.insert("driver", zvariant::Value::new(v));
        }
        if let Some(v) = &self.path {
            ret.insert("path", zvariant::Value::new(v));
        }
        if let Some(v) = &self.kernel_command_line {
            ret.insert("kernel-command-line", zvariant::Value::new(v));
        }
        Ok(ret)
    }
}
