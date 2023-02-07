// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{
    state::get_json_value_difference, ErrorKind, MergedNetworkState,
    MergedOvsDbGlobalConfig, NmstateError, OvsBridgeConfig, OvsBridgeInterface,
    OvsDbGlobalConfig, OvsInterface,
};

impl MergedOvsDbGlobalConfig {
    pub(crate) fn verify(
        &self,
        current: &OvsDbGlobalConfig,
    ) -> Result<(), NmstateError> {
        let external_ids: HashMap<String, Option<String>> = self
            .external_ids
            .iter()
            .filter(|(_, v)| !v.is_none())
            .map(|(k, v)| (k.to_string(), v.clone()))
            .collect();
        let other_config: HashMap<String, Option<String>> = self
            .other_config
            .iter()
            .filter(|(_, v)| !v.is_none())
            .map(|(k, v)| (k.to_string(), v.clone()))
            .collect();
        let desired = OvsDbGlobalConfig {
            external_ids: Some(external_ids),
            other_config: Some(other_config),
            prop_list: vec!["external_ids", "other_config"],
        };

        let desired_value = serde_json::to_value(desired)?;
        let current_value = if current.is_none() {
            serde_json::to_value(OvsDbGlobalConfig {
                external_ids: Some(HashMap::new()),
                other_config: Some(HashMap::new()),
                prop_list: Vec::new(),
            })?
        } else {
            serde_json::to_value(current)?
        };

        if let Some((reference, desire, current)) = get_json_value_difference(
            "ovsdb".to_string(),
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

impl OvsBridgeConfig {
    pub(crate) fn update(&mut self, other: Option<&OvsBridgeConfig>) {
        if let Some(other) = other {
            self.ports = other.ports.clone();
        }
    }
}

impl OvsBridgeInterface {
    pub(crate) fn update_ovs_bridge(&mut self, other: &OvsBridgeInterface) {
        if let Some(br_conf) = &mut self.bridge {
            br_conf.update(other.bridge.as_ref());
        } else {
            self.bridge = other.bridge.clone();
        }
    }
}

impl OvsInterface {
    pub(crate) fn update_ovs_iface(&mut self, other: &Self) {
        if other.patch.is_some() {
            self.patch = other.patch.clone();
        }
        if other.dpdk.is_some() {
            self.dpdk = other.dpdk.clone();
        }
    }
}

impl MergedNetworkState {
    // Sine desire `ovsdb: {}` means remove all, we cannot
    // differentiate it with `ovsdb` not defined due to `serde(default)`.
    // Hence we need to check `MergedNetworkState.prop_list`.
    pub(crate) fn is_global_ovsdb_changed(&self) -> bool {
        if self.prop_list.contains(&"ovsdb") {
            if self.ovsdb.desired.is_none() {
                true
            } else {
                let cur_external_ids = self
                    .ovsdb
                    .current
                    .external_ids
                    .as_ref()
                    .cloned()
                    .unwrap_or_default();
                let cur_other_config = self
                    .ovsdb
                    .current
                    .other_config
                    .as_ref()
                    .cloned()
                    .unwrap_or_default();

                self.ovsdb.external_ids != cur_external_ids
                    || self.ovsdb.other_config != cur_other_config
            }
        } else {
            false
        }
    }
}
