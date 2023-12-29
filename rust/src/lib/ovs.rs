// SPDX-License-Identifier: Apache-2.0

use std::collections::{BTreeMap, HashMap};

use serde::{Deserialize, Deserializer, Serialize, Serializer};

use crate::{ErrorKind, MergedOvnConfiguration, NmstateError};

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
        self.external_ids.is_none() && self.other_config.is_none()
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
    pub(crate) external_ids: HashMap<String, Option<String>>,
    pub(crate) other_config: HashMap<String, Option<String>>,
    pub(crate) is_changed: bool,
}

impl MergedOvsDbGlobalConfig {
    // Partial editing for ovsdb:
    //  * Merge desire with current and do overriding.
    //  * Use `ovsdb: {}` to remove all settings.
    //  * To remove a key from existing, use `foo: None`.
    pub(crate) fn new(
        mut desired: Option<OvsDbGlobalConfig>,
        current: OvsDbGlobalConfig,
        merged_ovn: &MergedOvnConfiguration,
    ) -> Result<Self, NmstateError> {
        let mut external_ids: HashMap<String, Option<String>> = HashMap::new();
        let mut other_config: HashMap<String, Option<String>> = HashMap::new();

        let empty_map: HashMap<String, Option<String>> = HashMap::new();

        let mut cur_external_ids: HashMap<String, Option<String>> =
            current.external_ids.as_ref().unwrap_or(&empty_map).clone();

        let cur_other_config: HashMap<String, Option<String>> =
            current.other_config.as_ref().unwrap_or(&empty_map).clone();

        if let Some(desired) = &mut desired {
            if !desired.is_purge() {
                desired.sanitize()?;

                merge_ovsdb_confs(
                    desired.external_ids.as_ref(),
                    current.external_ids.as_ref().unwrap_or(&empty_map),
                    &mut external_ids,
                );

                merge_ovsdb_confs(
                    desired.other_config.as_ref(),
                    current.other_config.as_ref().unwrap_or(&empty_map),
                    &mut other_config,
                );
            }
        } else {
            external_ids = cur_external_ids.clone();
            other_config = cur_other_config.clone();
        }

        if let Some(v) = merged_ovn.to_ovsdb_external_id_value() {
            external_ids.insert(
                OvsDbGlobalConfig::OVN_BRIDGE_MAPPINGS_KEY.to_string(),
                Some(v),
            );
        }

        if let Some(v) = merged_ovn.current.to_ovsdb_external_id_value() {
            cur_external_ids.insert(
                OvsDbGlobalConfig::OVN_BRIDGE_MAPPINGS_KEY.to_string(),
                Some(v),
            );
        }

        let is_changed = cur_other_config != other_config
            || cur_external_ids != external_ids;

        Ok(Self {
            desired,
            current,
            external_ids,
            other_config,
            is_changed,
        })
    }
}

fn merge_ovsdb_confs(
    desired: Option<&HashMap<String, Option<String>>>,
    current: &HashMap<String, Option<String>>,
    output: &mut HashMap<String, Option<String>>,
) {
    if let Some(desired) = desired {
        // User want to purge this section
        if desired.is_empty() {
            return;
        }

        let removed_keys: Vec<&str> = desired
            .iter()
            .filter_map(
                |(k, v)| if v.is_none() { Some(k.as_str()) } else { None },
            )
            .collect();

        for (cur_k, cur_v) in current.iter() {
            if let Some(cur_v) = cur_v {
                if !removed_keys.contains(&cur_k.as_str()) {
                    output.insert(cur_k.to_string(), Some(cur_v.to_string()));
                }
            }
        }
        for (des_k, des_v) in desired.iter() {
            if let Some(des_v) = des_v {
                output.insert(des_k.to_string(), Some(des_v.to_string()));
            }
        }
    } else {
        // User never mentioned this section, hence copy from current
        for (cur_k, cur_v) in current.iter() {
            output.insert(cur_k.to_string(), cur_v.clone());
        }
    }
}
