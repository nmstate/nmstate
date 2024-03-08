// SPDX-License-Identifier: Apache-2.0

use crate::{HsrConfig, HsrInterface};

impl HsrInterface {
    pub(crate) fn update_hsr(&mut self, other: &HsrInterface) {
        if let Some(hsr_conf) = &mut self.hsr {
            hsr_conf.update(other.hsr.as_ref());
        } else {
            self.hsr.clone_from(&other.hsr);
        }
    }

    pub(crate) fn sanitize_desired_for_verify(&mut self) {
        if let Some(conf) = &mut self.hsr {
            conf.supervision_address = None;
        }
    }
}

impl HsrConfig {
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.port1.clone_from(&other.port1);
            self.port2.clone_from(&other.port2);
            self.supervision_address
                .clone_from(&other.supervision_address);
            self.multicast_spec = other.multicast_spec;
            self.protocol = other.protocol;
        }
    }
}
