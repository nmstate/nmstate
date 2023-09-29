// SPDX-License-Identifier: Apache-2.0

use crate::{MergedRouteRules, NmstateFeature};

impl MergedRouteRules {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        if self.desired.config.is_some() {
            vec![NmstateFeature::StaticRouteRule]
        } else {
            Vec::new()
        }
    }
}
