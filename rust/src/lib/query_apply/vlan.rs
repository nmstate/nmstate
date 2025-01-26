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

    // When VLAN Qos changed only from or to, we should include the whole map
    // instead of changed.
    pub(crate) fn include_diff_context(
        &mut self,
        desired: &VlanInterface,
        current: &VlanInterface,
    ) {
        if let (Some(des_conf), Some(cur_conf)) =
            (desired.vlan.as_ref(), current.vlan.as_ref())
        {
            // If changed, always include VLAN ID and base-iface as context
            if des_conf != cur_conf {
                let new_conf = VlanConfig {
                    id: des_conf.id,
                    base_iface: des_conf
                        .base_iface
                        .clone()
                        .or_else(|| cur_conf.base_iface.clone()),
                    ..Default::default()
                };
                self.vlan = Some(new_conf);
            }
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
