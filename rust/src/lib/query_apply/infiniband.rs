// SPDX-License-Identifier: Apache-2.0

use crate::{InfiniBandConfig, InfiniBandInterface};

impl InfiniBandInterface {
    pub(crate) fn update_ib(&mut self, other: &InfiniBandInterface) {
        if let Some(ib_conf) = &mut self.ib {
            ib_conf.update(other.ib.as_ref());
        } else {
            self.ib = other.ib.clone();
        }
    }
}

impl InfiniBandConfig {
    pub(crate) fn update(&mut self, other: Option<&InfiniBandConfig>) {
        if let Some(other) = other {
            self.mode = other.mode;
            self.pkey = other.pkey;
            self.base_iface = other.base_iface.clone();
        }
    }
}
