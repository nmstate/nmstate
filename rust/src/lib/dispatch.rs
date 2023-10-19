// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{ErrorKind, MergedInterfaces, NmstateError};

#[derive(Debug, Clone, PartialEq, Eq, Default, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct DispatchConfig {
    /// Dispatch bash script content to be invoked after interface activation
    /// finished by network backend. Nmstate will append additional lines
    /// to make sure this script is only invoked for specified interface when
    /// backend interface activation finished.
    /// Setting to empty string will remove the dispatch script
    #[serde(skip_serializing_if = "Option::is_none")]
    pub post_activation: Option<String>,
    /// Dispatch bash script content to be invoked after interface deactivation
    /// finished by network backend. Nmstate will append additional lines
    /// to make sure this script is only invoked for specified interface when
    /// backend interface deactivation finished.
    /// Setting to empty string will remove the dispatch script
    #[serde(skip_serializing_if = "Option::is_none")]
    pub post_deactivation: Option<String>,
}

impl MergedInterfaces {
    pub(crate) fn validate_dispatch_script_has_no_checkpoint(
        &self,
    ) -> Result<(), NmstateError> {
        if self.kernel_ifaces.values().any(|i| {
            i.is_desired()
                && i.for_apply
                    .as_ref()
                    .map(|f| f.base_iface().dispatch.is_some())
                    .unwrap_or_default()
        }) {
            if self.gen_conf_mode {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Dispatch script is not supported in gc(gen_conf) mode"
                        .to_string(),
                ));
            } else {
                log::info!(
                    "Dispatch script is not protected by checkpoint, please \
                    backup your original nmstate created dispatch scripts"
                )
            }
        }
        Ok(())
    }
}
