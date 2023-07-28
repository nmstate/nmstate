// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Default, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct DispatchConfig {
    /// Dispatch bash script content to be invoked after interface activation
    /// finished by network backend. Nmstate will append additional lines
    /// to make sure this script is only invoked for specified interface when
    /// backend interface activation finished.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub post_activation: Option<String>,
    /// Dispatch bash script content to be invoked after interface deactivation
    /// finished by network backend. Nmstate will append additional lines
    /// to make sure this script is only invoked for specified interface when
    /// backend interface deactivation finished.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub post_deactivation: Option<String>,
}
