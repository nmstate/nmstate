// SPDX-License-Identifier: Apache-2.0

use crate::{VxlanConfig, VxlanInterface};

impl VxlanInterface {
    pub(crate) fn update_vxlan(&mut self, other: &VxlanInterface) {
        // TODO: this should be done by Trait
        if let Some(vxlan_conf) = &mut self.vxlan {
            vxlan_conf.update(other.vxlan.as_ref());
        } else {
            self.vxlan.clone_from(&other.vxlan);
        }
    }
}

impl VxlanConfig {
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.base_iface.clone_from(&other.base_iface);
            self.id = other.id;
            self.learning = other.learning;
            self.local = other.local;
            self.remote = other.remote;
            self.dst_port = other.dst_port;
        }
    }
}
