// SPDX-License-Identifier: Apache-2.0

use crate::{MergedRouteRules, NmstateFeature};

impl MergedRouteRules {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        if let Some(rts) = self.desired.config.as_ref() {
            if !rts.is_empty() {
                let mut ret = vec![NmstateFeature::StaticRouteRule];
                if rts.iter().any(|r| {
                    (!r.is_absent()) && r.suppress_prefix_length.is_some()
                }) {
                    ret.push(
                        NmstateFeature::StaticRouteRuleSuppressPrefixLength,
                    );
                }
                ret
            } else {
                Vec::new()
            }
        } else {
            Vec::new()
        }
    }
}
