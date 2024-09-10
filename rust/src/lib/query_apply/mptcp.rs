// SPDX-License-Identifier: Apache-2.0

use crate::MptcpConfig;

impl MptcpConfig {
    pub(crate) fn sanitize_desired_for_verify(&mut self) {
        if let Some(flags) = self.address_flags.as_mut() {
            flags.dedup();
            flags.sort_unstable();
        }
    }

    pub(crate) fn sanitize_current_for_verify(&mut self) {
        let flags = self.address_flags.get_or_insert(Default::default());
        flags.dedup();
        flags.sort_unstable();
    }
}
