// SPDX-License-Identifier: Apache-2.0

use crate::{IpVlanConfig, IpVlanInterface};

impl IpVlanInterface {
    pub(crate) fn update_ipvlan(&mut self, other: &IpVlanInterface) {
        if let Some(conf) = &mut self.ipvlan {
            conf.update(other.ipvlan.as_ref());
        } else {
            self.ipvlan.clone_from(&other.ipvlan);
        }
    }
}

impl IpVlanConfig {
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.base_iface.clone_from(&other.base_iface);
            self.mode = other.mode;
            self.private = other.private;
            self.vepa = other.vepa;
        }
    }
}
