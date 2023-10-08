// SPDX-License-Identifier: Apache-2.0

use crate::{MergedNetworkState, NetworkState, NmstateError};

impl NetworkState {
    pub fn generate_revert(
        &self,
        current: &Self,
    ) -> Result<Self, NmstateError> {
        let merged_state = MergedNetworkState::new(
            self.clone(),
            current.clone(),
            false,
            false,
        )?;
        Ok(Self {
            interfaces: merged_state.interfaces.generate_revert()?,
            routes: merged_state.routes.generate_revert(),
            rules: merged_state.rules.generate_revert(),
            dns: merged_state.dns.generate_revert(),
            ovsdb: merged_state.ovsdb.generate_revert(),
            ovn: merged_state.ovn.generate_revert(),
            hostname: merged_state.hostname.generate_revert(),
            prop_list: vec!["interfaces"],
            ..Default::default()
        })
    }
}
