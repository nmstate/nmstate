// SPDX-License-Identifier: Apache-2.0

use crate::{
    state::get_json_value_difference, ErrorKind, MergedOvnConfiguration,
    NmstateError, OvnConfiguration,
};

impl MergedOvnConfiguration {
    pub(crate) fn verify(
        &self,
        current: &OvnConfiguration,
    ) -> Result<(), NmstateError> {
        let mut desired = self.desired.clone();
        if let Some(maps) = desired.bridge_mappings.as_mut() {
            maps.retain(|map| !map.is_absent());
            maps.sort_unstable();
        }

        let mut current = current.clone();
        if let Some(maps) = current.bridge_mappings.as_mut() {
            // Only keep desired in new current to verify
            maps.retain(|map| {
                desired
                    .bridge_mappings
                    .as_ref()
                    .map(|des_maps| {
                        des_maps
                            .iter()
                            .any(|des_map| des_map.localnet == map.localnet)
                    })
                    .unwrap_or_default()
            });
            maps.sort_unstable();
        } else {
            current.bridge_mappings = Some(Vec::new());
        }

        let desired_value = serde_json::to_value(desired)?;
        let current_value = serde_json::to_value(current)?;

        if let Some((reference, desire, current)) = get_json_value_difference(
            "ovn".to_string(),
            &desired_value,
            &current_value,
        ) {
            Err(NmstateError::new(
                ErrorKind::VerificationError,
                format!(
                    "Verification failure: {reference} desire '{desire}', \
                    current '{current}'"
                ),
            ))
        } else {
            Ok(())
        }
    }
}
