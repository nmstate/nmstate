// SPDX-License-Identifier: Apache-2.0

use crate::DispatchConfig;

impl DispatchConfig {
    // For current in verify, None means empty string
    pub(crate) fn sanitize_current_for_verify(&mut self) {
        if self.post_activation.is_none() {
            self.post_activation = Some(String::new());
        }
        if self.post_deactivation.is_none() {
            self.post_deactivation = Some(String::new());
        }
    }
}
