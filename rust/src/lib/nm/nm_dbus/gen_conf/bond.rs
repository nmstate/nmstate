use std::collections::HashMap;

use zvariant::Value;

use super::super::{NmError, NmSettingBond, ToKeyfile};

impl ToKeyfile for NmSettingBond {
    fn to_keyfile(&self) -> Result<HashMap<String, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        for (key, value) in self.options.iter() {
            ret.insert(key.to_string(), Value::new(value));
        }
        Ok(ret)
    }
}
