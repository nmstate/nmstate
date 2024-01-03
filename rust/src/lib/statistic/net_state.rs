// SPDX-License-Identifier: Apache-2.0

use serde::Serialize;

use crate::{MergedNetworkState, NetworkState, NmstateError, NmstateFeature};

#[derive(Clone, Debug, Serialize, Default, PartialEq, Eq)]
#[non_exhaustive]
pub struct NmstateStatistic {
    pub topology: Vec<String>,
    pub features: Vec<NmstateFeature>,
}

impl NetworkState {
    pub fn statistic(
        &self,
        current: &Self,
    ) -> Result<NmstateStatistic, NmstateError> {
        let mut current = current.clone();
        let mut features = Vec::new();

        // The MergedNetworkState will try to resolve SRIOV VF names,
        // To detect IfaceNameReferedBySriovVfId feature, we need to
        // do it before MergedNetworkState
        if self.interfaces.has_sriov_naming() {
            features.push(NmstateFeature::IfaceNameReferedBySriovVfId);
            // Need to use pseudo VF interface to bypass all checks in
            // MergedNetworkState::new().
            self.interfaces
                .use_pseudo_sriov_vf_name(&mut current.interfaces);
        }
        let merged_state =
            MergedNetworkState::new(self.clone(), current, false)?;

        features.append(&mut merged_state.interfaces.get_features());
        features.append(&mut merged_state.dns.get_features());
        features.append(&mut merged_state.routes.get_features());
        features.append(&mut merged_state.rules.get_features());
        features.append(&mut merged_state.ovsdb.get_features());
        features.append(&mut merged_state.ovn.get_features());
        features.append(&mut merged_state.hostname.get_features());

        features.sort_unstable();

        Ok(NmstateStatistic {
            topology: merged_state.interfaces.gen_topoligies(),
            features,
        })
    }
}
