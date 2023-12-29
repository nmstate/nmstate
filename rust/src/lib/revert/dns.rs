// SPDX-License-Identifier: Apache-2.0

use crate::{DnsState, MergedDnsState};

impl MergedDnsState {
    pub(crate) fn generate_revert(&self) -> Option<DnsState> {
        if self.is_changed() {
            Some(self.current.clone())
        } else {
            None
        }
    }
}
