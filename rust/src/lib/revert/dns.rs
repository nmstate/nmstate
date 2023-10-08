// SPDX-License-Identifier: Apache-2.0

use crate::{DnsState, MergedDnsState};

impl MergedDnsState {
    pub(crate) fn generate_revert(&self) -> DnsState {
        if self.is_changed() {
            self.current.clone()
        } else {
            DnsState::new()
        }
    }
}
