// SPDX-License-Identifier: Apache-2.0

use crate::{HostNameState, MergedHostNameState};

impl MergedHostNameState {
    pub(crate) fn generate_revert(&self) -> Option<HostNameState> {
        if self.desired.is_some() {
            self.current.clone()
        } else {
            None
        }
    }
}
