// SPDX-License-Identifier: Apache-2.0

use crate::MergedInterface;

impl MergedInterface {
    pub(crate) fn get_ip_topology(&self) -> Option<String> {
        let mut ret: Vec<&str> = Vec::new();
        if let Some(ip4) = self.merged.base_iface().ipv4.as_ref() {
            if ip4.is_static() {
                ret.push("static_ip4")
            }
            if ip4.is_auto() {
                ret.push("auto_ip4")
            }
        }
        if let Some(ip6) = self.merged.base_iface().ipv6.as_ref() {
            if ip6.is_static() {
                ret.push("static_ip6")
            }
            if ip6.is_auto() {
                ret.push("auto_ip6")
            }
        }

        if ret.is_empty() {
            None
        } else {
            Some(ret.as_slice().join(","))
        }
    }
}
