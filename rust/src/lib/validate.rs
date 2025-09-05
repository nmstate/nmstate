// SPDX-License-Identifier: Apache-2.0

use crate::{
    MergedNetworkState, NetworkPolicy, NetworkState, NetworkStateMode,
    NmstateError,
};

impl NetworkState {
    /// Validate specified NetworkState without apply
    ///
    /// When `cur_state` set to `Some(NetworkState)`, this function will
    /// perform identical pre-apply validation as
    /// [NetworkState::apply_async()].
    /// When `cur_state` set to None, nmstate will preform best-effort
    /// validations due to the lacking of real hardware access.
    pub fn validate(
        &self,
        cur_state: Option<&NetworkState>,
    ) -> Result<(), NmstateError> {
        if let Some(cur_state) = cur_state {
            MergedNetworkState::new(
                self.clone(),
                cur_state.clone(),
                NetworkStateMode::Apply,
                false, // not memory only
            )?;
        } else {
            self.gen_conf()?;
        }
        Ok(())
    }
}

impl NetworkPolicy {
    /// Validate specified NetworkPolicy without apply
    ///
    /// When `NetworkPolicy.current` set to `Some(NetworkState)`, this function
    /// will perform identical pre-apply validation as
    /// [NetworkState::apply_async()] and
    /// `NetworkState::try_from(NetworkPolicy)`
    /// When `NetworkPolicy.current` set to None, nmstate will perform
    /// best-effort validations due to the lacking of real hardware access.
    pub fn validate(&self) -> Result<(), NmstateError> {
        if self.current.is_some() {
            let policy = self.clone();
            let desired_state = NetworkState::try_from(policy)?;
            desired_state.validate(self.current.as_ref())
        } else {
            // TODO (Gris Ge): Currently, it is very complex to
            // generate pseudo current state base on `NetworkCaptureRules`,
            // we just do nothing here for now.
            Ok(())
        }
    }
}
