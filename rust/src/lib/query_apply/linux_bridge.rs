// SPDX-License-Identifier: Apache-2.0

use crate::{LinuxBridgeConfig, LinuxBridgeInterface};

impl LinuxBridgeInterface {
    pub(crate) const INTEGER_ROUNDED_OPTIONS: [&'static str; 5] = [
        "interface.bridge.options.multicast-last-member-interval",
        "interface.bridge.options.multicast-membership-interval",
        "interface.bridge.options.multicast-querier-interval",
        "interface.bridge.options.multicast-query-response-interval",
        "interface.bridge.options.multicast-startup-query-interval",
    ];

    pub(crate) fn update_bridge(&mut self, other: &LinuxBridgeInterface) {
        if let Some(br_conf) = &mut self.bridge {
            br_conf.update(other.bridge.as_ref());
        } else {
            self.bridge = other.bridge.clone();
        }
    }

    // With 250 kernel HZ(Ubuntu kernel) and 100 user HZ, some linux bridge
    // kernel option value will be rounded up with 1 difference which lead to
    // verification error.
    pub(crate) fn is_interger_rounded_up(prop_full_name: &str) -> bool {
        for allowed_prop_name in &Self::INTEGER_ROUNDED_OPTIONS {
            if prop_full_name.ends_with(allowed_prop_name) {
                return true;
            }
        }
        false
    }
}

impl LinuxBridgeConfig {
    pub(crate) fn update(&mut self, other: Option<&LinuxBridgeConfig>) {
        if let Some(other) = other {
            self.options = other.options.clone();
            self.port = other.port.clone();
        }
    }
}
