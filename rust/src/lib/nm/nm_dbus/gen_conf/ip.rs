// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use super::super::{NmError, NmSettingIp, ToDbusValue, ToKeyfile};

impl ToKeyfile for NmSettingIp {
    fn to_keyfile(&self) -> Result<HashMap<String, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        for (k, v) in self.to_value()?.drain() {
            if !["address-data", "route-data", "dns", "routing-rules"]
                .contains(&k)
            {
                ret.insert(k.to_string(), v);
            }
        }
        for (i, addr) in self.addresses.as_slice().iter().enumerate() {
            ret.insert(format!("address{i}"), zvariant::Value::new(addr));
        }

        for (i, route) in self.routes.as_slice().iter().enumerate() {
            for (k, v) in route.to_keyfile().drain() {
                ret.insert(
                    if k.is_empty() {
                        format!("route{i}")
                    } else {
                        format!("route{i}_{k}")
                    },
                    zvariant::Value::new(v),
                );
            }
        }
        for (i, rule) in self.route_rules.as_slice().iter().enumerate() {
            for (_, v) in rule.to_keyfile().drain() {
                ret.insert(format!("routing-rule{i}"), zvariant::Value::new(v));
            }
        }
        if let Some(dns) = self.dns.as_ref() {
            ret.insert("dns".to_string(), zvariant::Value::new(dns));
        }

        Ok(ret)
    }
}
