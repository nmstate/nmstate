// SPDX-License-Identifier: Apache-2.0

use std::collections::{BTreeMap, HashSet};
use std::convert::{TryFrom, TryInto};

use serde::{Deserialize, Serialize};

use crate::{ErrorKind, NmstateError};

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
/// Global OVN bridge mapping configuration. Example yaml output of
/// [crate::NetworkState]:
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
    const SEPARATOR: &'static str = ",";

    pub(crate) fn is_none(&self) -> bool {
        self.bridge_mappings.is_none()
    }

    pub(crate) fn sanitize(&mut self) -> Result<(), NmstateError> {
        self.sanitize_unique_localnet_keys()?;
        if let Some(maps) = self.bridge_mappings.as_deref_mut() {
            for map in maps {
                map.sanitize()?;
            }
        }
        Ok(())
    }

    fn sanitize_unique_localnet_keys(&self) -> Result<(), NmstateError> {
        if let Some(maps) = self.bridge_mappings.as_deref() {
            let localnet_keys: Vec<&str> =
                maps.iter().map(|m| m.localnet.as_str()).collect();
            for map in maps {
                if localnet_keys
                    .iter()
                    .filter(|k| k == &&map.localnet.as_str())
                    .count()
                    > 1
                {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Found duplicate `localnet` key {}",
                            map.localnet
                        ),
                    ));
                }
            }
        }
        Ok(())
    }

    pub(crate) fn to_ovsdb_external_id_value(&self) -> Option<String> {
        if let Some(maps) = self.bridge_mappings.as_ref() {
            let mut maps = maps.clone();
            maps.dedup();
            maps.sort_unstable();
            if maps.is_empty() {
                None
            } else {
                Some(
                    maps.as_slice()
                        .iter()
                        .map(|map| map.to_string())
                        .collect::<Vec<String>>()
                        .join(Self::SEPARATOR),
                )
            }
        } else {
            None
        }
    }
}

impl TryFrom<&str> for OvnConfiguration {
    type Error = NmstateError;

    fn try_from(maps_str: &str) -> Result<Self, NmstateError> {
        let mut maps = Vec::new();
        for map_str in maps_str.split(Self::SEPARATOR) {
            if !map_str.is_empty() {
                maps.push(map_str.try_into()?);
            }
        }
        maps.dedup();
        maps.sort_unstable();

        Ok(Self {
            bridge_mappings: if maps.is_empty() { None } else { Some(maps) },
        })
    }
}

// The OVN is just syntax sugar wrapping single entry in ovsdb `external_ids`
// section.
// Before sending to backends for applying, we store it into
// `MergedOvsDbGlobalConfig` as normal `external_ids` entry.
// When receiving from backend for querying, we use
// `NetworkState::isolate_ovn()` to isolate this `external_ids` entry
// into `OvnConfiguration`.
// For verification, we are treating it as normal property without extracting.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MergedOvnConfiguration {
    pub(crate) desired: OvnConfiguration,
    pub(crate) current: OvnConfiguration,
    ovsdb_ext_id_value: Option<String>,
}

impl MergedOvnConfiguration {
    pub(crate) fn to_ovsdb_external_id_value(&self) -> Option<String> {
        self.ovsdb_ext_id_value.clone()
    }

    // Partial editing for ovn:
    //  * Merge desire with current and do overriding.
    //  * To remove a particular ovn-bridge-mapping, do `state: absent`
    pub(crate) fn new(
        desired: OvnConfiguration,
        current: OvnConfiguration,
    ) -> Result<Self, NmstateError> {
        let mut desired = desired;
        desired.sanitize()?;

        let empty_vec: Vec<OvnBridgeMapping> = Vec::new();
        let deleted_localnets: HashSet<&str> = desired
            .bridge_mappings
            .as_ref()
            .unwrap_or(&empty_vec)
            .iter()
            .filter_map(|m| {
                if m.is_absent() {
                    Some(m.localnet.as_str())
                } else {
                    None
                }
            })
            .collect();
        let mut desired_ovn_maps: BTreeMap<&str, &str> = BTreeMap::new();

        for cur_map in current.bridge_mappings.as_ref().unwrap_or(&empty_vec) {
            if let Some(cur_br) = cur_map.bridge.as_deref() {
                if !deleted_localnets.contains(&cur_map.localnet.as_str()) {
                    desired_ovn_maps.insert(cur_map.localnet.as_str(), cur_br);
                }
            }
        }
        for des_map in desired.bridge_mappings.as_ref().unwrap_or(&empty_vec) {
            if let Some(des_br) = des_map.bridge.as_deref() {
                if !des_map.is_absent() {
                    desired_ovn_maps.insert(des_map.localnet.as_str(), des_br);
                }
            }
        }

        let ovsdb_ext_id_value = OvnConfiguration {
            bridge_mappings: Some(
                desired_ovn_maps
                    .iter()
                    .map(|(k, v)| OvnBridgeMapping {
                        localnet: k.to_string(),
                        bridge: Some(v.to_string()),
                        ..Default::default()
                    })
                    .collect(),
            ),
        }
        .to_ovsdb_external_id_value();

        Ok(Self {
            desired,
            current,
            ovsdb_ext_id_value,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[non_exhaustive]
pub struct OvnBridgeMapping {
    pub localnet: String,
    #[serde(skip_serializing)]
    /// When set to `state: absent`, will delete the existing
    /// `localnet` mapping.
    pub state: Option<OvnBridgeMappingState>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bridge: Option<String>,
}

// For Ord
impl PartialOrd for OvnBridgeMapping {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

// For Vec::sort_unstable()
impl Ord for OvnBridgeMapping {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.sort_key().cmp(&other.sort_key())
    }
}

impl TryFrom<&str> for OvnBridgeMapping {
    type Error = NmstateError;

    fn try_from(map_str: &str) -> Result<Self, NmstateError> {
        let items: Vec<&str> = map_str.split(Self::SEPARATOR).collect();
        if items.len() != 2 || items[1].is_empty() || items[0].is_empty() {
            Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Cannot convert {map_str} to OvnBridgeMapping, \
                    expected format is `<localnet>{}<bridge>`",
                    Self::SEPARATOR
                ),
            ))
        } else {
            Ok(Self {
                localnet: items[0].to_string(),
                bridge: Some(items[1].to_string()),
                ..Default::default()
            })
        }
    }
}

impl OvnBridgeMapping {
    const SEPARATOR: &'static str = ":";

    pub(crate) fn is_absent(&self) -> bool {
        self.state == Some(OvnBridgeMappingState::Absent)
    }

    fn sort_key(&self) -> (bool, &str, Option<&str>) {
        (
            // We want absent mapping listed before others
            !self.is_absent(),
            self.localnet.as_str(),
            self.bridge.as_deref(),
        )
    }

    pub fn sanitize(&mut self) -> Result<(), NmstateError> {
        if !self.is_absent() {
            self.state = None;
        }
        if (!self.is_absent()) && self.bridge.is_none() {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "mapping for `localnet` key {} missing the \
                    `bridge` attribute",
                    self.localnet
                ),
            ));
        }
        Ok(())
    }
}

impl std::fmt::Display for OvnBridgeMapping {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if let Some(bridge) = self.bridge.as_ref() {
            write!(f, "{}:{}", self.localnet, bridge,)
        } else {
            write!(f, "",)
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase", deny_unknown_fields)]
#[non_exhaustive]
pub enum OvnBridgeMappingState {
    #[deprecated(since = "2.2.17", note = "No state means present")]
    Present,
    Absent,
}
