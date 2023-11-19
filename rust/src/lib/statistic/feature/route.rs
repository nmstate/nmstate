// SPDX-License-Identifier: Apache-2.0

use crate::{MergedRoutes, NmstateFeature};

impl MergedRoutes {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        if self.desired.config.is_some() {
            vec![NmstateFeature::StaticRoute]
        } else {
            Vec::new()
        }
    }
}
