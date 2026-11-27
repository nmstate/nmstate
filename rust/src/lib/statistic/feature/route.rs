// SPDX-License-Identifier: Apache-2.0

use crate::{MergedRoutes, NmstateFeature};

impl MergedRoutes {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        let has_authoritative_scope = self
            .desired
            .authoritative
            .as_ref()
            .is_some_and(|scopes| !scopes.is_empty());
        if self.desired.config.is_some() || has_authoritative_scope {
            vec![NmstateFeature::StaticRoute]
        } else {
            Vec::new()
        }
    }
}
