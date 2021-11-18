use crate::dbus_value::{own_value_to_string, own_value_to_u32};
use crate::NmError;
use std::collections::HashMap;
use std::convert::TryFrom;

#[derive(Debug, Clone, PartialEq, Default)]
pub struct NmSettingVlan {
    pub parent: Option<String>,
    pub id: Option<u32>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<HashMap<String, zvariant::OwnedValue>> for NmSettingVlan {
    type Error = NmError;
    fn try_from(
        mut setting_value: HashMap<String, zvariant::OwnedValue>,
    ) -> Result<Self, Self::Error> {
        let mut setting = Self::new();
        setting.parent = setting_value
            .remove("parent")
            .map(own_value_to_string)
            .transpose()?;
        setting.id = setting_value
            .remove("id")
            .map(own_value_to_u32)
            .transpose()?;
        setting._other = setting_value;
        Ok(setting)
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
