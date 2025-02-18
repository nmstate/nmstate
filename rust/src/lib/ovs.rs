// SPDX-License-Identifier: Apache-2.0

use std::collections::{BTreeMap, HashMap};

use serde::{Deserialize, Deserializer, Serialize, Serializer};

use crate::{ErrorKind, NmstateError};

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
pub struct OvsDbGlobalConfig {
    #[serde(
        skip_serializing_if = "Option::is_none",
        serialize_with = "show_as_ordered_map"
    )]
    // When the value been set as None, specified key will be removed instead
    // of merging.
    // To remove all settings of external_ids or other_config, use empty
    // HashMap
    pub external_ids: Option<HashMap<String, Option<String>>>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        serialize_with = "show_as_ordered_map"
    )]
    pub other_config: Option<HashMap<String, Option<String>>>,
}

impl OvsDbGlobalConfig {
    pub(crate) const OVN_BRIDGE_MAPPINGS_KEY: &'static str =
        "ovn-bridge-mappings";

    // User want to remove all settings except OVN.
    pub(crate) fn is_purge(&self) -> bool {
        match (self.external_ids.as_ref(), self.other_config.as_ref()) {
            (None, None) => true,
            (Some(eids), Some(oids)) => eids.is_empty() && oids.is_empty(),
            _ => false,
        }
    }

    pub(crate) fn sanitize(&self) -> Result<(), NmstateError> {
        if self
            .external_ids
            .as_ref()
            .map(|e| e.contains_key(Self::OVN_BRIDGE_MAPPINGS_KEY))
            == Some(true)
        {
            Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "The `{}` is reserved for OVN mapping, please use \
                    `ovn` section instead of `ovs-db` section",
                    Self::OVN_BRIDGE_MAPPINGS_KEY
                ),
            ))
        } else {
            Ok(())
        }
    }
}

fn show_as_ordered_map<S>(
    v: &Option<HashMap<String, Option<String>>>,
    s: S,
) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    if let Some(v) = v {
        let ordered: BTreeMap<_, _> = v.iter().collect();
        ordered.serialize(s)
    } else {
        s.serialize_none()
    }
}

impl OvsDbGlobalConfig {
    pub fn is_none(&self) -> bool {
        self.external_ids.is_none() && self.other_config.is_none()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize)]
#[non_exhaustive]
pub struct OvsDbIfaceConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub external_ids: Option<HashMap<String, Option<String>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// OpenvSwitch specific `other_config`. Please refer to
    /// manpage `ovs-vswitchd.conf.db(5)` for more detail.
    /// When setting to None, nmstate will try to preserve current
    /// `other_config`, otherwise, nmstate will override all `other_config`
    /// for specified interface.
    pub other_config: Option<HashMap<String, Option<String>>>,
}

impl OvsDbIfaceConfig {
    pub(crate) fn get_external_ids(&self) -> HashMap<&str, &str> {
        let mut ret = HashMap::new();
        if let Some(eids) = self.external_ids.as_ref() {
            for (k, v) in eids {
                if let Some(v) = v {
                    ret.insert(k.as_str(), v.as_str());
                }
            }
        }
        ret
    }

    pub(crate) fn get_other_config(&self) -> HashMap<&str, &str> {
        let mut ret = HashMap::new();
        if let Some(cfgs) = self.other_config.as_ref() {
            for (k, v) in cfgs {
                if let Some(v) = v {
                    ret.insert(k.as_str(), v.as_str());
                }
            }
        }
        ret
    }
}

impl<'de> Deserialize<'de> for OvsDbIfaceConfig {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let mut ret = Self::default();
        let mut v = serde_json::Value::deserialize(deserializer)?;
        if let Some(v) = v.as_object_mut() {
            if let Some(v) = v.remove("external_ids") {
                ret.external_ids = Some(value_to_hash_map(&v));
            }
            if let Some(v) = v.remove("other_config") {
                ret.other_config = Some(value_to_hash_map(&v));
            }
            if !v.is_empty() {
                let remain_keys: Vec<String> = v.keys().cloned().collect();
                return Err(serde::de::Error::custom(format!(
                    "Unsupported section names '{}', only supports \
                    `external_ids` and `other_config`",
                    remain_keys.join(", ")
                )));
            }
        } else {
            return Err(serde::de::Error::custom(format!(
                "Expecting dict/HashMap, but got {v:?}"
            )));
        }
        Ok(ret)
    }
}

fn value_to_hash_map(
    value: &serde_json::Value,
) -> HashMap<String, Option<String>> {
    let mut ret: HashMap<String, Option<String>> = HashMap::new();
    if let Some(value) = value.as_object() {
        for (k, v) in value.iter() {
            let v = match &v {
                serde_json::Value::Number(i) => Some({
                    if let Some(i) = i.as_i64() {
                        format!("{i}")
                    } else if let Some(i) = i.as_u64() {
                        format!("{i}")
                    } else if let Some(i) = i.as_f64() {
                        format!("{i}")
                    } else {
                        continue;
                    }
                }),
                serde_json::Value::String(s) => Some(s.to_string()),
                serde_json::Value::Bool(b) => Some(format!("{b}")),
                serde_json::Value::Null => None,
                _ => continue,
            };
            ret.insert(k.to_string(), v);
        }
    }
    ret
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MergedOvsDbGlobalConfig {
    pub(crate) desired: Option<OvsDbGlobalConfig>,
    pub(crate) current: OvsDbGlobalConfig,
}

impl MergedOvsDbGlobalConfig {
    pub(crate) fn new(
        mut desired: Option<OvsDbGlobalConfig>,
        current: OvsDbGlobalConfig,
    ) -> Result<Self, NmstateError> {
        if let Some(desired) = desired.as_mut() {
            if !desired.is_purge() {
                desired.sanitize()?;
            }
        }
        Ok(Self { desired, current })
    }
}
