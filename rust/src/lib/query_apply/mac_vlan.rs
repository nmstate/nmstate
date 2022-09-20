// SPDX-License-Identifier: Apache-2.0

use crate::{MacVlanConfig, MacVlanInterface};

impl MacVlanInterface {
    pub(crate) fn update_mac_vlan(&mut self, other: &MacVlanInterface) {
        // TODO: this should be done by Trait
        if let Some(conf) = &mut self.mac_vlan {
            conf.update(other.mac_vlan.as_ref());
        } else {
            self.mac_vlan = other.mac_vlan.clone();
        }
    }
}

impl MacVlanConfig {
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.base_iface = other.base_iface.clone();
            self.mode = other.mode;
            self.accept_all_mac = other.accept_all_mac;
        }
    }
}
