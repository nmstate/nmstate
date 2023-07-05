// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::ovn::OVN_BRIDGE_MAPPINGS;
use crate::ErrorKind::InvalidArgument;
use crate::NmstateError;
use serde::{Deserialize, Deserializer, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize)]
#[non_exhaustive]
pub struct OvsDbGlobalConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    // When the value been set as None, specified key will be removed instead
    // of merging.
    // To remove all settings of external_ids or other_config, use empty
    // HashMap
    pub external_ids: Option<HashMap<String, Option<String>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub other_config: Option<HashMap<String, Option<String>>>,
    #[serde(skip)]
    pub(crate) prop_list: Vec<&'static str>,
}

impl OvsDbGlobalConfig {
    pub fn is_none(&self) -> bool {
        self.external_ids.is_none() && self.other_config.is_none()
    }
}

impl<'de> Deserialize<'de> for OvsDbGlobalConfig {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let mut ret = Self::default();
        let v = serde_json::Value::deserialize(deserializer)?;
        if let Some(v) = v.as_object() {
            if let Some(v) = v.get("external_ids") {
                ret.prop_list.push("external_ids");
                ret.external_ids = Some(value_to_hash_map(v));
            }
            if let Some(v) = v.get("other_config") {
                ret.prop_list.push("other_config");
                ret.other_config = Some(value_to_hash_map(v));
            }
        } else {
            return Err(serde::de::Error::custom(format!(
                "Expecting dict/HashMap, but got {v:?}"
            )));
        }
        Ok(ret)
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
        let v = serde_json::Value::deserialize(deserializer)?;
        if let Some(v) = v.as_object() {
            if let Some(v) = v.get("external_ids") {
                ret.external_ids = Some(value_to_hash_map(v));
            }
            if let Some(v) = v.get("other_config") {
                ret.other_config = Some(value_to_hash_map(v));
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
    pub(crate) desired: OvsDbGlobalConfig,
    pub(crate) current: OvsDbGlobalConfig,
    pub(crate) external_ids: HashMap<String, Option<String>>,
    pub(crate) other_config: HashMap<String, Option<String>>,
}

impl MergedOvsDbGlobalConfig {
    // Partial editing for ovsdb:
    //  * Merge desire with current and do overriding.
    //  * Use `ovsdb: {}` to remove all settings.
    //  * To remove a key from existing, use `foo: None`.
    pub(crate) fn new(
        desired: OvsDbGlobalConfig,
        current: OvsDbGlobalConfig,
    ) -> Result<Self, NmstateError> {
        if desired.prop_list.is_empty() {
            // User want to remove all settings
            Ok(Self {
                desired,
                current,
                external_ids: HashMap::new(),
                other_config: HashMap::new(),
            })
        } else {
            let mut external_ids =
                current.external_ids.as_ref().cloned().unwrap_or_default();
            let mut other_config =
                current.other_config.as_ref().cloned().unwrap_or_default();

            if let Some(ex_ids) = desired.external_ids.as_ref() {
                if ex_ids.is_empty() {
                    external_ids.clear();
                } else {
                    if ex_ids.get(OVN_BRIDGE_MAPPINGS).is_some() {
                        const INVALID_EXTERNAL_IDS_KEY: &str = "Cannot use the `ovn-bridge-mappings`\
                         external_ids key directly. Please use ovn.bridge-mappings API instead";
                        return Err(NmstateError::new(
                            InvalidArgument,
                            INVALID_EXTERNAL_IDS_KEY.to_string(),
                        ));
                    }
                    for (k, v) in ex_ids {
                        if v.is_none() {
                            external_ids.remove(k);
                        } else {
                            external_ids.insert(k.clone(), v.clone());
                        }
                    }
                }
            }

            if let Some(cfgs) = desired.other_config.as_ref() {
                if cfgs.is_empty() {
                    other_config.clear();
                } else {
                    for (k, v) in cfgs {
                        if v.is_none() {
                            other_config.remove(k);
                        } else {
                            other_config.insert(k.clone(), v.clone());
                        }
                    }
                }
            }

            Ok(Self {
                desired,
                current,
                external_ids,
                other_config,
            })
        }
    }
}
