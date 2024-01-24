// SPDX-License-Identifier: Apache-2.0

use crate::{HsrConfig, HsrInterface};

impl HsrInterface {
    pub(crate) fn update_hsr(&mut self, other: &HsrInterface) {
        if let Some(hsr_conf) = &mut self.hsr {
            hsr_conf.update(other.hsr.as_ref());
        } else {
            self.hsr = other.hsr.clone();
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
            self.port1 = other.port1.clone();
            self.port2 = other.port2.clone();
            self.supervision_address = other.supervision_address.clone();
            self.multicast_spec = other.multicast_spec;
            self.protocol = other.protocol;
        }
    }
}
