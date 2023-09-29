// SPDX-License-Identifier: Apache-2.0

use serde::Serialize;

use crate::{MergedNetworkState, NetworkState, NmstateError, NmstateFeature};

#[derive(Clone, Debug, Serialize, Default, PartialEq, Eq)]
#[non_exhaustive]
pub struct NmstateStatistic {
    topology: Vec<String>,
    features: Vec<NmstateFeature>,
}

impl NetworkState {
    pub fn statistic(
        &self,
        current: &Self,
    ) -> Result<NmstateStatistic, NmstateError> {
        let merged_state = MergedNetworkState::new(
            self.clone(),
            current.clone(),
            false,
            false,
        )?;

        let mut features = merged_state.interfaces.get_features();
        features.append(&mut merged_state.dns.get_features());
        features.append(&mut merged_state.routes.get_features());
        features.append(&mut merged_state.rules.get_features());
        features.append(&mut merged_state.ovsdb.get_features());
        features.append(&mut merged_state.ovn.get_features());
        features.append(&mut merged_state.hostname.get_features());

        Ok(NmstateStatistic {
            topology: merged_state.interfaces.gen_topoligies(),
            features,
        })
    }
}
