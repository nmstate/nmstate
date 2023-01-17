// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use super::super::{
    NmError, NmSettingOvsBridge, NmSettingOvsDpdk, NmSettingOvsExtIds,
    NmSettingOvsIface, NmSettingOvsOtherConfig, NmSettingOvsPatch,
    NmSettingOvsPort, ToKeyfile,
};

impl ToKeyfile for NmSettingOvsBridge {}
impl ToKeyfile for NmSettingOvsPort {}
impl ToKeyfile for NmSettingOvsIface {}
impl ToKeyfile for NmSettingOvsPatch {}
impl ToKeyfile for NmSettingOvsDpdk {}

impl ToKeyfile for NmSettingOvsExtIds {
    fn to_keyfile(&self) -> Result<HashMap<String, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(data) = self.data.as_ref() {
            for (k, v) in data {
                ret.insert(format!("data.{k}"), zvariant::Value::new(v));
            }
        }
        Ok(ret)
    }
}

impl ToKeyfile for NmSettingOvsOtherConfig {
    fn to_keyfile(&self) -> Result<HashMap<String, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(data) = self.data.as_ref() {
            for (k, v) in data {
                ret.insert(format!("data.{k}"), zvariant::Value::new(v));
            }
        }
        Ok(ret)
    }
}
