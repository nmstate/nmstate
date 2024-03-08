// SPDX-License-Identifier: Apache-2.0

use crate::{InfiniBandConfig, InfiniBandInterface};

impl InfiniBandInterface {
    pub(crate) fn update_ib(&mut self, other: &InfiniBandInterface) {
        if let Some(ib_conf) = &mut self.ib {
            ib_conf.update(other.ib.as_ref());
        } else {
            self.ib.clone_from(&other.ib);
        }
    }
}

impl InfiniBandConfig {
    pub(crate) fn update(&mut self, other: Option<&InfiniBandConfig>) {
        if let Some(other) = other {
            self.mode = other.mode;
            self.pkey = other.pkey;
            self.base_iface.clone_from(&other.base_iface);
        }
    }
}
