// SPDX-License-Identifier: Apache-2.0
use std::collections::HashMap;

use zvariant::Value;

use super::super::{NmError, NmSettingWired, ToDbusValue, ToKeyfile};

impl ToKeyfile for NmSettingWired {
    fn to_keyfile(&self) -> Result<HashMap<String, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        for (k, v) in self.to_value()?.drain() {
            if k != "cloned-mac-address" {
                ret.insert(k.to_string(), v);
            }
        }
        if let Some(v) = &self.cloned_mac_address {
            ret.insert("cloned-mac-address".to_string(), Value::new(v));
        }
        Ok(ret)
    }
}
