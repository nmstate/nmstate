// SPDX-License-Identifier: Apache-2.0

use crate::{MergedHostNameState, NmstateFeature};

impl MergedHostNameState {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        if self.desired.as_ref().map(|d| d.config.is_some()) == Some(true) {
            vec![NmstateFeature::StaticHostname]
        } else {
            Vec::new()
        }
    }
}
