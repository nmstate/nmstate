use crate::connection::DbusDictionary;
use crate::dbus_value::{own_value_to_string, own_value_to_u32};
use crate::NmError;
use serde::Deserialize;
use std::collections::HashMap;
use std::convert::TryFrom;

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
pub struct NmSettingVlan {
    pub parent: Option<String>,
    pub id: Option<u32>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingVlan {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            parent: _from_map!(v, "parent", own_value_to_string)?,
            id: _from_map!(v, "id", own_value_to_u32)?,
            _other: v,
        })
    }
}

impl NmSettingVlan {
    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.parent {
            ret.insert("parent", zvariant::Value::new(v.clone()));
        }
        if let Some(id) = self.id {
            ret.insert("id", zvariant::Value::new(id));
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
