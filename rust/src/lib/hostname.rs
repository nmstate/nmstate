// SPDX-License-Identifier: Apache-2.0
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
pub struct HostNameState {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub running: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub config: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub(crate) struct MergedHostNameState {
    pub(crate) desired: Option<HostNameState>,
    pub(crate) current: Option<HostNameState>,
}

impl MergedHostNameState {
    pub(crate) fn new(
        desired: Option<HostNameState>,
        current: Option<HostNameState>,
    ) -> Self {
        Self { desired, current }
    }
}
