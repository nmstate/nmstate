// SPDX-License-Identifier: Apache-2.0

use std::collections::{HashMap, HashSet};

use crate::ovn::OVN_BRIDGE_MAPPINGS;
use crate::{
    state::get_json_value_difference, ErrorKind, Interface, InterfaceState,
    InterfaceType, Interfaces, MergedInterfaces, MergedNetworkState,
    MergedOvsDbGlobalConfig, NmstateError, OvsBridgeBondConfig,
    OvsBridgeConfig, OvsBridgeInterface, OvsDbGlobalConfig, OvsDbIfaceConfig,
    OvsInterface,
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
            .filter(|(k, _)| !k.as_str().eq(OVN_BRIDGE_MAPPINGS))
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
    pub(crate) fn sanitize_current_for_verify(&mut self) {
        if let Some(port_confs) = self
            .bridge
            .as_mut()
            .and_then(|br_conf| br_conf.ports.as_mut())
        {
            for port_conf in port_confs {
                if let Some(bond_conf) = port_conf.bond.as_mut() {
                    bond_conf.sanitize_current_for_verify();
                }
            }
        }
    }

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
        if self.prop_list.contains(&"ovsdb") || self.prop_list.contains(&"ovn")
        {
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

                let cur_bridge_mappings = self
                    .ovn
                    .current
                    .bridge_mappings
                    .as_ref()
                    .cloned()
                    .unwrap_or_default();

                self.ovsdb.external_ids != cur_external_ids
                    || self.ovsdb.other_config != cur_other_config
                    || self.ovn.bridge_mappings != cur_bridge_mappings
            }
        } else {
            false
        }
    }
}

impl OvsDbIfaceConfig {
    pub(crate) fn new_empty() -> Self {
        Self {
            external_ids: Some(HashMap::new()),
            other_config: Some(HashMap::new()),
        }
    }
}

impl OvsBridgeBondConfig {
    pub(crate) fn sanitize_current_for_verify(&mut self) {
        // None ovsbd equal to empty
        if self.ovsdb.is_none() {
            self.ovsdb = Some(OvsDbIfaceConfig::new_empty());
        }
    }
}
impl MergedInterfaces {
    // This function remove extra(undesired) ovs patch port from post-apply
    // current, so it will not interfere with verification
    pub(crate) fn process_allow_extra_ovs_patch_ports_for_verify(
        &self,
        current: &mut Interfaces,
    ) {
        let mut ovs_patch_port_names: HashSet<String> = HashSet::new();
        for cur_iface in current.iter().filter_map(|i| {
            if let Interface::OvsInterface(o) = i {
                Some(o)
            } else {
                None
            }
        }) {
            if cur_iface.is_ovs_patch_port() {
                ovs_patch_port_names.insert(cur_iface.base.name.to_string());
            }
        }

        for des_iface in self.iter().filter_map(|i| {
            if let Some(Interface::OvsBridge(o)) = i.desired.as_ref() {
                if o.bridge.as_ref().map(|c| c.allow_extra_patch_ports)
                    == Some(true)
                    && o.base.state == InterfaceState::Up
                {
                    Some(o)
                } else {
                    None
                }
            } else {
                None
            }
        }) {
            if let Some(cur_iface) = current.get_iface_mut(
                des_iface.base.name.as_str(),
                InterfaceType::OvsBridge,
            ) {
                let mut ports_to_delete: HashSet<String> = HashSet::new();
                if let (Some(des_ports), Some(cur_ports)) =
                    (des_iface.ports(), cur_iface.ports())
                {
                    for cur_port_name in cur_ports {
                        if ovs_patch_port_names.contains(cur_port_name)
                            && !des_ports.contains(&cur_port_name)
                        {
                            ports_to_delete.insert(cur_port_name.to_string());
                        }
                    }
                }
                for port_name in ports_to_delete.iter() {
                    cur_iface.remove_port(port_name);
                }
            }
        }
    }
}
