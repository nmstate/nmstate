// SPDX-License-Identifier: Apache-2.0

use crate::ovn::{MergedOvnConfiguration, OvnBridgeMapping};
use crate::state::get_json_value_difference;
use crate::ErrorKind::InvalidArgument;
use crate::{ErrorKind, NmstateError, OvnConfiguration};
use std::str::FromStr;

impl MergedOvnConfiguration {
    pub(crate) fn verify(
        &self,
        current: &OvnConfiguration,
    ) -> Result<(), NmstateError> {
        let mut ovn_bridge_mappings: Vec<OvnBridgeMapping> =
            self.bridge_mappings.clone();

        let desired = OvnConfiguration {
            bridge_mappings: match ovn_bridge_mappings.is_empty() {
                true => None,
                false => {
                    ovn_bridge_mappings
                        .sort_by(|v1, v2| v1.localnet.cmp(&v2.localnet));
                    Some(ovn_bridge_mappings)
                }
            },
        };

        let desired_value = serde_json::to_value(desired)?;
        let current_value = if current.is_none() {
            serde_json::to_value(OvnConfiguration {
                bridge_mappings: Some(Vec::new()),
            })?
        } else {
            serde_json::to_value(current)?
        };

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

pub fn string_to_ovn_bridge_mappings(
    mappings_string: String,
) -> Result<Vec<OvnBridgeMapping>, NmstateError> {
    if mappings_string.is_empty() {
        return Ok(Vec::default());
    }
    let mut mappings: Vec<OvnBridgeMapping> = Vec::new();
    for mapping_str in mappings_string.split(',') {
        match OvnBridgeMapping::from_str(mapping_str) {
            Ok(mapping) => mappings.push(mapping),
            Err(e) => {
                return Err(NmstateError::new(InvalidArgument, e.to_string()))
            }
        }
    }
    if mappings.is_empty() {
        Ok(Vec::default())
    } else {
        Ok(mappings)
    }
}
