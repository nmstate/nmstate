// SPDX-License-Identifier: Apache-2.0

use std::collections::hash_map::Entry;
use std::collections::HashMap;

use serde::{
    ser::SerializeTuple, Deserialize, Deserializer, Serialize, Serializer,
};

use crate::{ErrorKind, NmstateError};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
/// Bridge VLAN filtering configuration
pub struct BridgePortVlanConfig {
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    /// Enable native VLAN.
    /// Deserialize and serialize from/to `enable-native`.
    pub enable_native: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Bridge VLAN filtering mode
    pub mode: Option<BridgePortVlanMode>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u16_or_string"
    )]
    /// VLAN Tag for native VLAN.
    pub tag: Option<u16>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        serialize_with = "bridge_trunk_tags_serialize"
    )]
    /// Trunk tags.
    /// Deserialize and serialize from/to `trunk-tags`.
    pub trunk_tags: Option<Vec<BridgePortTrunkTag>>,
}

impl BridgePortVlanConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn is_changed(&self, current: &Self) -> bool {
        (self.enable_native.is_some()
            && self.enable_native != current.enable_native)
            || (self.mode.is_some() && self.mode != current.mode)
            || (self.tag.is_some() && self.tag != current.tag)
            || (self.trunk_tags.is_some()
                && self.trunk_tags != current.trunk_tags)
    }

    pub(crate) fn is_empty(&self) -> bool {
        self.enable_native.is_none()
            && self.mode.is_none()
            && self.tag.is_none()
            && self.trunk_tags.is_none()
    }

    pub(crate) fn sort_trunk_tags(&mut self) {
        if let Some(trunk_tags) = self.trunk_tags.as_mut() {
            trunk_tags.sort_unstable_by(|tag_a, tag_b| match (tag_a, tag_b) {
                (BridgePortTrunkTag::Id(a), BridgePortTrunkTag::Id(b)) => {
                    a.cmp(b)
                }
                _ => {
                    log::warn!(
                        "Please call flatten_vlan_ranges() \
                        before sort_port_vlans()"
                    );
                    std::cmp::Ordering::Equal
                }
            })
        }
    }

    pub(crate) fn flatten_vlan_ranges(&mut self) {
        if let Some(trunk_tags) = &self.trunk_tags {
            let mut new_trunk_tags = Vec::new();
            for trunk_tag in trunk_tags {
                match trunk_tag {
                    BridgePortTrunkTag::Id(_) => {
                        new_trunk_tags.push(trunk_tag.clone())
                    }
                    BridgePortTrunkTag::IdRange(range) => {
                        for i in range.min..range.max + 1 {
                            new_trunk_tags.push(BridgePortTrunkTag::Id(i));
                        }
                    }
                };
            }
            self.trunk_tags = Some(new_trunk_tags);
        }
    }

    pub(crate) fn sanitize(
        &self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if is_desired {
            if self.mode == Some(BridgePortVlanMode::Trunk)
                && self.tag.is_some()
                && self.tag != Some(0)
                && self.enable_native != Some(true)
            {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Bridge VLAN filtering `tag` cannot be use \
                    in trunk mode without `enable-native`"
                        .to_string(),
                ));
            }

            if self.mode == Some(BridgePortVlanMode::Access)
                && self.enable_native == Some(true)
            {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Bridge VLAN filtering `enable-native: true` \
                    cannot be set in access mode"
                        .to_string(),
                ));
            }

            if self.mode == Some(BridgePortVlanMode::Access) {
                if let Some(tags) = self.trunk_tags.as_ref() {
                    if !tags.is_empty() {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            "Bridge VLAN filtering access mode cannot have \
                            trunk-tags defined"
                                .to_string(),
                        ));
                    }
                }
            }

            if self.mode == Some(BridgePortVlanMode::Trunk)
                && self.trunk_tags.is_none()
            {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Bridge VLAN filtering trunk mode cannot have \
                empty trunk-tags"
                        .to_string(),
                ));
            }
            if let Some(tags) = self.trunk_tags.as_ref() {
                validate_overlap_trunk_tags(tags)?;
            }
        }

        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum BridgePortVlanMode {
    /// Trunk mode
    Trunk,
    /// Access mode
    Access,
}

impl Default for BridgePortVlanMode {
    fn default() -> Self {
        Self::Access
    }
}

impl std::fmt::Display for BridgePortVlanMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Trunk => "trunk",
                Self::Access => "access",
            }
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum BridgePortTrunkTag {
    #[serde(deserialize_with = "crate::deserializer::u16_or_string")]
    /// Single VLAN trunk ID
    Id(u16),
    /// VLAN trunk ID range
    IdRange(BridgePortVlanRange),
}

impl std::fmt::Display for BridgePortTrunkTag {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Id(d) => write!(f, "id={d}"),
            Self::IdRange(range) => {
                write!(f, "id-range=[{},{}]", range.min, range.max)
            }
        }
    }
}

impl<'de> Deserialize<'de> for BridgePortTrunkTag {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let v = serde_json::Value::deserialize(deserializer)?;
        if let Some(id) = v.get("id") {
            if let Some(id) = id.as_str() {
                Ok(Self::Id(id.parse::<u16>().map_err(|e| {
                    serde::de::Error::custom(format!(
                        "Failed to parse BridgePortTrunkTag id \
                        {id} as u16: {e}"
                    ))
                })?))
            } else if let Some(id) = id.as_u64() {
                Ok(Self::Id(u16::try_from(id).map_err(|e| {
                    serde::de::Error::custom(format!(
                        "Failed to parse BridgePortTrunkTag id \
                        {id} as u16: {e}"
                    ))
                })?))
            } else {
                Err(serde::de::Error::custom(format!(
                    "The id of BridgePortTrunkTag should be \
                    unsigned 16 bits integer, but got {v}"
                )))
            }
        } else if let Some(id_range) = v.get("id-range") {
            Ok(Self::IdRange(
                BridgePortVlanRange::deserialize(id_range)
                    .map_err(serde::de::Error::custom)?,
            ))
        } else {
            Err(serde::de::Error::custom(format!(
                "BridgePortTrunkTag only support 'id' or 'id-range', \
                but got {v}"
            )))
        }
    }
}

fn bridge_trunk_tags_serialize<S>(
    tags: &Option<Vec<BridgePortTrunkTag>>,
    serializer: S,
) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    if let Some(tags) = tags {
        let mut serial_list = serializer.serialize_tuple(tags.len())?;
        for tag in tags {
            match tag {
                BridgePortTrunkTag::Id(id) => {
                    let mut map = HashMap::new();
                    map.insert("id", id);
                    serial_list.serialize_element(&map)?;
                }
                BridgePortTrunkTag::IdRange(id_range) => {
                    let mut map = HashMap::new();
                    map.insert("id-range", id_range);
                    serial_list.serialize_element(&map)?;
                }
            }
        }
        serial_list.end()
    } else {
        serializer.serialize_none()
    }
}

impl BridgePortTrunkTag {
    pub fn get_vlan_tag_range(&self) -> (u16, u16) {
        match self {
            Self::Id(min) => (*min, *min),
            Self::IdRange(range) => (range.min, range.max),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
pub struct BridgePortVlanRange {
    #[serde(deserialize_with = "crate::deserializer::u16_or_string")]
    /// Minimum VLAN ID(included).
    pub min: u16,
    #[serde(deserialize_with = "crate::deserializer::u16_or_string")]
    /// Maximum VLAN ID(included).
    pub max: u16,
}

fn validate_overlap_trunk_tags(
    tags: &[BridgePortTrunkTag],
) -> Result<(), NmstateError> {
    let mut found: HashMap<u16, &BridgePortTrunkTag> = HashMap::new();
    for tag in tags {
        match tag {
            BridgePortTrunkTag::Id(d) => match found.entry(*d) {
                Entry::Occupied(o) => {
                    let existing_tag = o.get();
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Bridge VLAN trunk tag {tag} is \
                            overlapping with other tag {existing_tag}"
                        ),
                    ));
                }
                Entry::Vacant(v) => {
                    v.insert(tag);
                }
            },

            BridgePortTrunkTag::IdRange(range) => {
                for i in range.min..range.max + 1 {
                    match found.entry(i) {
                        Entry::Occupied(o) => {
                            let existing_tag = o.get();
                            return Err(NmstateError::new(
                                ErrorKind::InvalidArgument,
                                format!(
                                    "Bridge VLAN trunk tag {tag} is \
                                    overlapping with other tag {existing_tag}"
                                ),
                            ));
                        }
                        Entry::Vacant(v) => {
                            v.insert(tag);
                        }
                    }
                }
            }
        }
    }
    Ok(())
}
