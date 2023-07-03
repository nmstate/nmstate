// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fmt;
use std::str::FromStr;

pub const OVN_BRIDGE_MAPPINGS: &str = "ovn-bridge-mappings";

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
/// Global OVN bridge mapping configuration. Example yaml output of [crate::NetworkState]:
/// ```yml
/// ---
/// ovn:
///   bridge-mappings:
///   - localnet: tenantblue
///     bridge: ovsbr1
///     state: present
///   - localnet: tenantred
///     bridge: ovsbr1
///     state: absent
/// ```
pub struct OvnConfiguration {
    #[serde(
        rename = "bridge-mappings",
        skip_serializing_if = "Option::is_none"
    )]
    pub bridge_mappings: Option<Vec<OvnBridgeMapping>>,
}

impl OvnConfiguration {
    pub fn is_none(&self) -> bool {
        self.bridge_mappings.is_none()
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MergedOvnConfiguration {
    pub(crate) desired: OvnConfiguration,
    pub(crate) current: OvnConfiguration,
    pub(crate) bridge_mappings: Vec<OvnBridgeMapping>,
    pub(crate) mappings_ext_id_value: Option<String>,
}

impl MergedOvnConfiguration {
    // Partial editing for ovn:
    //  * Merge desire with current and do overriding.
    //  * To remove a particular ovn-bridge-mapping, do `state: absent`
    pub(crate) fn new(
        desired: OvnConfiguration,
        current: OvnConfiguration,
    ) -> Self {
        let current_mappings: Vec<OvnBridgeMapping> =
            current.bridge_mappings.clone().unwrap_or_default();

        let mut indexed_current_mappings: HashMap<String, OvnBridgeMapping> =
            HashMap::new();
        for mapping in current_mappings.clone() {
            indexed_current_mappings
                .insert(mapping.clone().localnet, mapping.clone());
        }

        if let Some(mappings) = desired.bridge_mappings.clone() {
            for mapping in &mappings {
                indexed_current_mappings
                    .insert(mapping.clone().localnet, mapping.clone());
            }
        }

        let ovn_bridge_mappings: Vec<OvnBridgeMapping> =
            indexed_current_mappings
                .clone()
                .iter()
                .filter(|(_, v)| {
                    v.state.unwrap_or_default()
                        == OvnBridgeMappingState::Present
                })
                .map(|(_, v)| v.clone())
                .collect();

        if desired.clone().bridge_mappings.unwrap_or(Vec::new())
            != current_mappings
        {
            let updated_ovn_bridge_mappings_ext_ids_value: Option<String> =
                match ovn_bridge_mappings.is_empty() {
                    true => Some("".to_string()),
                    false => Some(ovn_bridge_mappings_to_string(
                        ovn_bridge_mappings.clone(),
                    )),
                };

            return Self {
                desired,
                current,
                bridge_mappings: ovn_bridge_mappings,
                mappings_ext_id_value:
                    updated_ovn_bridge_mappings_ext_ids_value,
            };
        }

        Self {
            desired,
            current,
            bridge_mappings: ovn_bridge_mappings,
            mappings_ext_id_value: None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct OvnBridgeMapping {
    pub localnet: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub state: Option<OvnBridgeMappingState>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bridge: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OvnBridgeMappingError {
    mapping_wannabe: String,
}

impl std::error::Error for OvnBridgeMappingError {}
impl OvnBridgeMappingError {
    fn new(reason: &str) -> Self {
        Self {
            mapping_wannabe: reason.to_string(),
        }
    }
}
impl fmt::Display for OvnBridgeMappingError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(
            f,
            "expected `<localnet>:<bridge>`, got: {}",
            self.mapping_wannabe
        )
    }
}

impl FromStr for OvnBridgeMapping {
    type Err = OvnBridgeMappingError;
    fn from_str(s: &str) -> Result<OvnBridgeMapping, OvnBridgeMappingError> {
        let vec: Vec<&str> = s.split(':').collect();
        if vec.len() != 2 {
            return Err(OvnBridgeMappingError::new(s));
        }
        let physnet: String = vec[0].to_string();
        let bridge: String = vec[1].to_string();
        if physnet.is_empty() || bridge.is_empty() {
            return Err(OvnBridgeMappingError::new(s));
        }
        Ok(OvnBridgeMapping {
            localnet: physnet,
            bridge: Some(bridge),
            state: Some(OvnBridgeMappingState::Present),
        })
    }
}

impl ToString for OvnBridgeMapping {
    fn to_string(&self) -> String {
        format!(
            "{}:{}",
            self.localnet,
            self.bridge.clone().unwrap_or("".to_string())
        )
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase", deny_unknown_fields)]
#[non_exhaustive]
pub enum OvnBridgeMappingState {
    Present,
    Absent,
}

impl Default for OvnBridgeMappingState {
    fn default() -> Self {
        Self::Present
    }
}

pub fn ovn_bridge_mappings_to_string(
    ovn_bridge_mappings: Vec<OvnBridgeMapping>,
) -> String {
    if ovn_bridge_mappings.is_empty() {
        return "".to_string();
    }
    ovn_bridge_mappings
        .iter()
        .filter(|mapping| mapping.bridge.is_some())
        .map(|mapping| mapping.to_string())
        .fold("".to_string(), |mappings, mapping| {
            if mappings.is_empty() {
                mapping
            } else {
                format!("{mappings},{mapping}")
            }
        })
}
