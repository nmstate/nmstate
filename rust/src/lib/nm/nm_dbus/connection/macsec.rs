// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use serde::Deserialize;

use super::super::{connection::DbusDictionary, NmError, ToDbusValue};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingMacSec {
    pub parent: Option<String>,
    pub mode: Option<i32>,
    pub encrypt: Option<bool>,
    pub mka_cak: Option<String>,
    pub mka_ckn: Option<String>,
    pub port: Option<i32>,
    pub validation: Option<i32>,
    pub send_sci: Option<bool>,
    pub offload: Option<i32>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingMacSec {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            parent: _from_map!(v, "parent", String::try_from)?,
            mode: _from_map!(v, "mode", i32::try_from)?,
            encrypt: _from_map!(v, "encrypt", bool::try_from)?,
            mka_ckn: _from_map!(v, "mka-ckn", String::try_from)?,
            port: _from_map!(v, "port", i32::try_from)?,
            validation: _from_map!(v, "validation", i32::try_from)?,
            send_sci: _from_map!(v, "send-sci", bool::try_from)?,
            mka_cak: None,
            offload: _from_map!(v, "offload", i32::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingMacSec {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.parent {
            ret.insert("parent", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.mode {
            ret.insert("mode", zvariant::Value::new(*v));
        }
        if let Some(v) = &self.encrypt {
            ret.insert("encrypt", zvariant::Value::new(*v));
        }
        if let Some(v) = &self.mka_cak {
            ret.insert("mka-cak", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.mka_ckn {
            ret.insert("mka-ckn", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.port {
            if *v > 0 {
                ret.insert("port", zvariant::Value::new(*v));
            }
        }
        if let Some(v) = &self.validation {
            ret.insert("validation", zvariant::Value::new(*v));
        }
        if let Some(v) = &self.send_sci {
            ret.insert("send-sci", zvariant::Value::new(*v));
        }
        if let Some(v) = self.offload {
            ret.insert("offload", zvariant::Value::new(v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

impl NmSettingMacSec {
    pub const OFFLOAD_OFF: i32 = 0;
    pub const OFFLOAD_PHY: i32 = 1;
    pub const OFFLOAD_MAC: i32 = 2;

    #[cfg(feature = "query_apply")]
    pub(crate) fn fill_secrets(&mut self, secrets: &DbusDictionary) {
        if let Some(v) = secrets.get("mka-cak") {
            match String::try_from(v.clone()) {
                Ok(s) => {
                    self.mka_cak = Some(s);
                }
                Err(e) => {
                    log::warn!(
                        "Failed to convert mka_cak: \
                        {:?} {:?}",
                        v,
                        e
                    );
                }
            }
        }
    }
}
