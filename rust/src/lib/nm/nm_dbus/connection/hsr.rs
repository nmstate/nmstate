use std::collections::HashMap;
use std::convert::TryFrom;

use serde::Deserialize;

use super::super::{connection::DbusDictionary, NmError, ToDbusValue};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingHsr {
    pub port1: Option<String>,
    pub port2: Option<String>,
    pub multicast_spec: Option<u32>,
    pub prp: Option<bool>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingHsr {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            port1: _from_map!(v, "port1", String::try_from)?,
            port2: _from_map!(v, "port2", String::try_from)?,
            multicast_spec: _from_map!(v, "multicast-spec", u32::try_from)?,
            prp: _from_map!(v, "prp", bool::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingHsr {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.port1 {
            ret.insert("port1", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.port2 {
            ret.insert("port2", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.multicast_spec {
            if *v > 0 {
                ret.insert("multicast-spec", zvariant::Value::new(*v));
            }
        }
        if let Some(v) = &self.prp {
            ret.insert("prp", zvariant::Value::new(*v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}
