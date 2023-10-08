// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{MergedOvsDbGlobalConfig, OvsDbGlobalConfig};

impl MergedOvsDbGlobalConfig {
    pub(crate) fn generate_revert(&self) -> OvsDbGlobalConfig {
        let mut revert_external_ids: HashMap<String, Option<String>> =
            HashMap::new();
        let empty_hash: HashMap<String, Option<String>> = HashMap::new();
        for eid_key in self
            .desired
            .external_ids
            .as_ref()
            .unwrap_or(&empty_hash)
            .keys()
        {
            revert_external_ids.insert(
                eid_key.to_string(),
                self.current
                    .external_ids
                    .as_ref()
                    .and_then(|c| c.get(eid_key))
                    .cloned()
                    .flatten(),
            );
        }

        let mut revert_other_configs: HashMap<String, Option<String>> =
            HashMap::new();
        let empty_hash: HashMap<String, Option<String>> = HashMap::new();
        for cfg_key in self
            .desired
            .other_config
            .as_ref()
            .unwrap_or(&empty_hash)
            .keys()
        {
            revert_other_configs.insert(
                cfg_key.to_string(),
                self.current
                    .other_config
                    .as_ref()
                    .and_then(|c| c.get(cfg_key))
                    .cloned()
                    .flatten(),
            );
        }

        if revert_external_ids.is_empty() && revert_other_configs.is_empty() {
            OvsDbGlobalConfig::default()
        } else {
            OvsDbGlobalConfig {
                external_ids: Some(revert_external_ids),
                other_config: Some(revert_other_configs),
                ..Default::default()
            }
        }
    }
}
