// SPDX-License-Identifier: Apache-2.0

use crate::{VrfConfig, VrfInterface};

impl VrfInterface {
    pub(crate) fn update_vrf(&mut self, other: &VrfInterface) {
        // TODO: this should be done by Trait
        if let Some(vrf_conf) = &mut self.vrf {
            vrf_conf.update(other.vrf.as_ref());
        } else {
            self.vrf = other.vrf.clone();
        }
    }
}

impl VrfConfig {
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.port = other.port.clone();
            self.table_id = other.table_id;
        }
    }
}
