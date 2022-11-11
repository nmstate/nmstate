// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::fmt::Write;

use super::super::{
    NmError, NmSettingSriov, NmSettingSriovVf, NmSettingSriovVfVlan,
    NmVlanProtocol, ToDbusValue, ToKeyfile,
};

impl ToKeyfile for NmSettingSriov {
    fn to_keyfile(&self) -> Result<HashMap<String, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        for (k, v) in self.to_value()?.drain() {
            if k != "vfs" {
                ret.insert(k.to_string(), v);
            }
        }
        if let Some(vfs) = self.vfs.as_ref() {
            for vf in vfs {
                if let Some(i) = vf.index {
                    ret.insert(
                        format!("vf.{i}"),
                        zvariant::Value::new(vf.to_keyfile()),
                    );
                }
            }
        }
        Ok(ret)
    }
}

impl NmSettingSriovVf {
    pub(crate) fn to_keyfile(&self) -> String {
        let mut ret = String::new();
        if let Some(v) = self.mac.as_ref() {
            let _ = write!(ret, "mac={v} ");
        }
        if let Some(v) = self.spoof_check {
            let _ = write!(ret, "spoof-check={v} ");
        }
        if let Some(v) = self.trust {
            let _ = write!(ret, "trust={v} ");
        }
        if let Some(v) = self.min_tx_rate {
            let _ = write!(ret, "min-tx-rate={v} ");
        }
        if let Some(v) = self.max_tx_rate {
            let _ = write!(ret, "max-tx-rate={v} ");
        }
        if let Some(vlans) = self.vlans.as_ref() {
            let mut vlans_str = Vec::new();
            for vlan in vlans {
                vlans_str.push(vlan.to_keyfile());
            }
            let _ = write!(ret, "vlans={}", vlans_str.join(";"));
        }
        if ret.ends_with(' ') {
            ret.pop();
        }
        ret
    }
}

impl NmSettingSriovVfVlan {
    pub(crate) fn to_keyfile(&self) -> String {
        match self.protocol {
            NmVlanProtocol::Dot1Q => format!("{}.{}.q", self.id, self.qos),
            NmVlanProtocol::Dot1Ad => format!("{}.{}.ad", self.id, self.qos),
        }
    }
}
