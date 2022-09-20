// SPDX-License-Identifier: Apache-2.0

use crate::{VxlanConfig, VxlanInterface};

impl VxlanInterface {
    pub(crate) fn update_vxlan(&mut self, other: &VxlanInterface) {
        // TODO: this should be done by Trait
        if let Some(vxlan_conf) = &mut self.vxlan {
            vxlan_conf.update(other.vxlan.as_ref());
        } else {
            self.vxlan = other.vxlan.clone();
        }
    }
}

impl VxlanConfig {
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.base_iface = other.base_iface.clone();
            self.id = other.id;
            self.remote = other.remote;
            self.dst_port = other.dst_port;
        }
    }
}
