// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use zvariant::Value;

use super::super::{
    NmError, NmSettingBridge, NmSettingBridgePort, NmSettingBridgeVlanRange,
    ToDbusValue, ToKeyfile,
};

impl ToKeyfile for NmSettingBridge {
    fn to_keyfile(&self) -> Result<HashMap<String, Value>, NmError> {
        let mut ret = HashMap::new();

        for (k, v) in self.to_value()?.drain() {
            if k != "vlans" {
                ret.insert(k.to_string(), v);
            }
        }
        if let Some(vlans) = self.vlans.as_ref() {
            let mut vlans_clone = vlans.clone();
            vlans_clone.sort_unstable_by_key(|v| v.vid_start);
            let mut vlans_str = Vec::new();
            for vlan in vlans_clone {
                vlans_str.push(vlan.to_keyfile());
            }
            ret.insert("vlans".to_string(), Value::new(vlans_str.join(",")));
        }

        Ok(ret)
    }
}

impl NmSettingBridgeVlanRange {
    fn to_keyfile(&self) -> String {
        let mut ret = if self.vid_start == self.vid_end {
            self.vid_start.to_string()
        } else {
            format!("{}-{}", self.vid_start, self.vid_end)
        };
        if self.pvid {
            ret += " pvid"
        }
        if self.untagged {
            ret += " untagged"
        }
        ret
    }
}

impl ToKeyfile for NmSettingBridgePort {
    fn to_keyfile(&self) -> Result<HashMap<String, Value>, NmError> {
        let mut ret = HashMap::new();

        for (k, v) in self.to_value()?.drain() {
            if k != "vlans" {
                ret.insert(k.to_string(), v);
            }
        }
        if let Some(vlans) = self.vlans.as_ref() {
            let mut vlans_clone = vlans.clone();
            vlans_clone.sort_unstable_by_key(|v| v.vid_start);
            let mut vlans_str = Vec::new();
            for vlan in vlans_clone {
                vlans_str.push(vlan.to_keyfile());
            }
            ret.insert("vlans".to_string(), Value::new(vlans_str.join(",")));
        }

        Ok(ret)
    }
}
