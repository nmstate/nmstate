// SPDX-License-Identifier: Apache-2.0

use crate::{VlanConfig, VlanInterface};

impl VlanInterface {
    pub(crate) fn update_vlan(&mut self, other: &VlanInterface) {
        // TODO: this should be done by Trait
        if let Some(vlan_conf) = &mut self.vlan {
            vlan_conf.update(other.vlan.as_ref());
        } else {
            self.vlan.clone_from(&other.vlan);
        }
    }
}

impl VlanConfig {
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.base_iface.clone_from(&other.base_iface);
            self.id = other.id;
            self.protocol = other.protocol;
        }
    }
}
