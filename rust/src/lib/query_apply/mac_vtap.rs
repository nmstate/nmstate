// SPDX-License-Identifier: Apache-2.0

use crate::{MacVtapConfig, MacVtapInterface};

impl MacVtapInterface {
    pub(crate) fn update_mac_vtap(&mut self, other: &MacVtapInterface) {
        // TODO: this should be done by Trait
        if let Some(conf) = &mut self.mac_vtap {
            conf.update(other.mac_vtap.as_ref());
        } else {
            self.mac_vtap = other.mac_vtap.clone();
        }
    }
}

impl MacVtapConfig {
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.base_iface = other.base_iface.clone();
            self.mode = other.mode;
            self.accept_all_mac = other.accept_all_mac;
        }
    }
}
