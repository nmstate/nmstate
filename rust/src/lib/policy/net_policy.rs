// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::{NetworkState, NmstateError};

use super::{NetworkCaptureRules, NetworkStateTemplate};

#[derive(Clone, Debug, Deserialize, Serialize, Default, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
#[non_exhaustive]
pub struct NetworkPolicy {
    #[serde(skip_serializing_if = "NetworkCaptureRules::is_empty", default)]
    /// Capture rules for matching current network state
    pub capture: NetworkCaptureRules,
    /// Template of desired state, will apply capture results
    #[serde(alias = "desiredState", default)]
    pub desired: NetworkStateTemplate,
    /// Current network state which the capture rules should run against
    #[serde(default)]
    pub current: Option<NetworkState>,
}

impl TryFrom<NetworkPolicy> for NetworkState {
    type Error = NmstateError;

    fn try_from(policy: NetworkPolicy) -> Result<Self, NmstateError> {
        if policy.is_empty() {
            return Ok(NetworkState::new());
        }

        if !policy.capture.is_empty() {
            let capture_results = match policy.current.as_ref() {
                Some(current) => policy.capture.execute(current)?,
                None => {
                    let mut current = NetworkState::new();
                    current.retrieve()?;
                    policy.capture.execute(&current)?
                }
            };
            policy.desired.fill_with_captured_data(&capture_results)
        } else {
            policy.desired.fill_with_captured_data(&HashMap::new())
        }
    }
}

impl NetworkPolicy {
    pub fn is_empty(&self) -> bool {
        self.capture.is_empty() && self.desired.is_empty()
    }
}
