// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use serde::Deserialize;

use super::super::{connection::DbusDictionary, NmError, ToDbusValue};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingVpn {
    pub data: Option<HashMap<String, String>>,
    pub service_type: Option<String>,
    pub persistent: Option<bool>,
    pub secrets: Option<HashMap<String, String>>,
    pub timeout: Option<u32>,
    pub user_name: Option<String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl NmSettingVpn {
    pub const SERVICE_TYPE_LIBRESWAN: &'static str =
        "org.freedesktop.NetworkManager.libreswan";
}

impl TryFrom<DbusDictionary> for NmSettingVpn {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            data: _from_map!(v, "data", <HashMap<String, String>>::try_from)?,
            service_type: _from_map!(v, "service-type", String::try_from)?,
            persistent: _from_map!(v, "persistent", bool::try_from)?,
            secrets: _from_map!(
                v,
                "secrets",
                <HashMap<String, String>>::try_from
            )?,
            timeout: _from_map!(v, "timeout", u32::try_from)?,
            user_name: _from_map!(v, "user-name", String::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingVpn {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.data {
            ret.insert("data", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = self.service_type.as_ref() {
            ret.insert("service-type", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = self.persistent.as_ref() {
            ret.insert("persistent", zvariant::Value::new(*v));
        }
        if let Some(v) = self.secrets.as_ref() {
            ret.insert("secrets", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = self.timeout.as_ref() {
            ret.insert("timeout", zvariant::Value::new(*v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

#[cfg(feature = "query_apply")]
impl NmSettingVpn {
    pub(crate) fn fill_secrets(&mut self, secrets: &DbusDictionary) {
        let mut ret: HashMap<String, String> = HashMap::new();
        for (k, v) in secrets {
            if let Ok(s) = String::try_from(v.clone()) {
                ret.insert(k.to_string(), s);
            }
        }
        self.secrets = secrets
            .get("secrets")
            .cloned()
            .and_then(|s| <HashMap<String, String>>::try_from(s).ok())
    }
}
