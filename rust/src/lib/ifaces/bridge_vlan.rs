// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use serde::{
    ser::SerializeTuple, Deserialize, Deserializer, Serialize, Serializer,
};

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
    pub trunk_tags: Option<Vec<BridgePortTunkTag>>,
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
pub enum BridgePortTunkTag {
    #[serde(deserialize_with = "crate::deserializer::u16_or_string")]
    /// Single VLAN trunk ID
    Id(u16),
    /// VLAN trunk ID range
    IdRange(BridgePortVlanRange),
}

impl<'de> Deserialize<'de> for BridgePortTunkTag {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let v = serde_json::Value::deserialize(deserializer)?;
        if let Some(id) = v.get("id") {
            if let Some(id) = id.as_str() {
                Ok(Self::Id(id.parse::<u16>().map_err(|e| {
                    serde::de::Error::custom(format!(
                        "Failed to parse BridgePortTunkTag id \
                        {id} as u16: {e}"
                    ))
                })?))
            } else if let Some(id) = id.as_u64() {
                Ok(Self::Id(u16::try_from(id).map_err(|e| {
                    serde::de::Error::custom(format!(
                        "Failed to parse BridgePortTunkTag id \
                        {id} as u16: {e}"
                    ))
                })?))
            } else {
                Err(serde::de::Error::custom(format!(
                    "The id of BridgePortTunkTag should be \
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
                "BridgePortTunkTag only support 'id' or 'id-range', \
                but got {v}"
            )))
        }
    }
}

fn bridge_trunk_tags_serialize<S>(
    tags: &Option<Vec<BridgePortTunkTag>>,
    serializer: S,
) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    if let Some(tags) = tags {
        let mut serial_list = serializer.serialize_tuple(tags.len())?;
        for tag in tags {
            match tag {
                BridgePortTunkTag::Id(id) => {
                    let mut map = HashMap::new();
                    map.insert("id", id);
                    serial_list.serialize_element(&map)?;
                }
                BridgePortTunkTag::IdRange(id_range) => {
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

impl BridgePortTunkTag {
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
