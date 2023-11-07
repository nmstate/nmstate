// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use zvariant::Value;

use super::super::{NmError, NmSettingVpn, ToDbusValue, ToKeyfile};

impl ToKeyfile for NmSettingVpn {
    fn to_keyfile(&self) -> Result<HashMap<String, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(vpn_data) = self.data.as_ref() {
            for (key, value) in vpn_data.iter() {
                ret.insert(key.to_string(), Value::new(value));
            }
        }
        for (k, v) in self
            .to_value()?
            .drain()
            .filter(|(k, _)| k != &"data" && k != &"secrets")
        {
            ret.insert(k.to_string(), v);
        }
        Ok(ret)
    }
}

impl NmSettingVpn {
    pub(crate) fn secrets_to_keyfile(
        &self,
    ) -> Option<HashMap<String, zvariant::Value>> {
        self.secrets.as_ref().map(|s| {
            s.iter()
                .map(|(k, v)| (k.to_string(), Value::new(v)))
                .collect()
        })
    }
}
