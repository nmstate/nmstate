// SPDX-License-Identifier: Apache-2.0

use crate::{Interface, VrfConfig, VrfInterface};

impl VrfInterface {
    pub(crate) fn update_vrf(&mut self, other: &VrfInterface) {
        // TODO: this should be done by Trait
        if let Some(vrf_conf) = &mut self.vrf {
            vrf_conf.update(other.vrf.as_ref());
        } else {
            self.vrf = other.vrf.clone();
        }
    }

    pub(crate) fn pre_verify_cleanup(
        &mut self,
        pre_apply_current: Option<&Interface>,
    ) {
        self.base.mac_address = None;
        if self.base.accept_all_mac_addresses == Some(false) {
            self.base.accept_all_mac_addresses = None;
        }
        if let Some(ports) = self.vrf.as_mut().and_then(|c| c.port.as_mut()) {
            ports.sort();
        }
        self.merge_table_id(pre_apply_current).ok();
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
