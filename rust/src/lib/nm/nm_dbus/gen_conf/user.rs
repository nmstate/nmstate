// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use zvariant::Value;

use super::super::{NmError, NmSettingUser, ToKeyfile};

impl ToKeyfile for NmSettingUser {
    fn to_keyfile(&self) -> Result<HashMap<String, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(data) = self.data.as_ref() {
            for (key, value) in data.iter() {
                ret.insert(key.to_string(), Value::new(value));
            }
        }
        Ok(ret)
    }
}
