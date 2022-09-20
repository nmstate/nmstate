// SPDX-License-Identifier: Apache-2.0

use crate::LldpConfig;

impl LldpConfig {
    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.neighbors = Vec::new();
    }
}
