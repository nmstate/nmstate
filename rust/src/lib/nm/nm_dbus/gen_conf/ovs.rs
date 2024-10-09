// SPDX-License-Identifier: Apache-2.0

use crate::nm::nm_dbus::ToDbusValue;
use std::collections::HashMap;

use super::super::{
    NmError, NmSettingOvsBridge, NmSettingOvsDpdk, NmSettingOvsExtIds,
    NmSettingOvsIface, NmSettingOvsOtherConfig, NmSettingOvsPatch,
    NmSettingOvsPort, ToKeyfile,
};

impl ToKeyfile for NmSettingOvsBridge {}
impl ToKeyfile for NmSettingOvsIface {}
impl ToKeyfile for NmSettingOvsPatch {}
impl ToKeyfile for NmSettingOvsDpdk {}

impl ToKeyfile for NmSettingOvsPort {
    fn to_keyfile(&self) -> Result<HashMap<String, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();

        for (k, v) in self.to_value()?.drain() {
            if k != "trunks" {
                ret.insert(k.to_string(), v);
            }
        }
        if let Some(vlans) = self.trunks.as_ref() {
            let mut vlans_clone = vlans.clone();
            vlans_clone.sort_unstable_by_key(|v| v.start);
            let mut vlans_str = Vec::new();
            for vlan in vlans_clone {
                let ret = if vlan.start == vlan.end {
                    vlan.start.to_string()
                } else {
                    format!("{}-{}", vlan.start, vlan.end)
                };
                vlans_str.push(ret);
            }
            ret.insert(
                "trunks".to_string(),
                zvariant::Value::new(vlans_str.join(",")),
            );
        }

        Ok(ret)
    }
}

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
