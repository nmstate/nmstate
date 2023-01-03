// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{
    state::get_json_value_difference, ErrorKind, NmstateError,
    OvsBridgeBondConfig, OvsBridgeConfig, OvsBridgeInterface,
    OvsBridgePortConfig, OvsDbGlobalConfig, OvsInterface,
};

impl OvsDbGlobalConfig {
    pub(crate) fn verify(&self, current: &Self) -> Result<(), NmstateError> {
        let self_value = serde_json::to_value(self)?;
        let current_value = serde_json::to_value(current)?;

        if let Some((reference, desire, current)) = get_json_value_difference(
            "ovsdb".to_string(),
            &self_value,
            &current_value,
        ) {
            let e = NmstateError::new(
                ErrorKind::VerificationError,
                format!(
                    "Verification failure: {reference} desire '{desire}', current '{current}'"
                ),
            );
            log::error!("{}", e);
            Err(e)
        } else {
            Ok(())
        }
    }

    // Partial editing for ovsdb:
    //  * Merge desire with current and do overriding.
    //  * Use `ovsdb: {}` to remove all settings.
    //  * To remove a key from existing, use `foo: None`.
    pub(crate) fn merge(&mut self, current: &Self) {
        if self.prop_list.is_empty() {
            // User want to remove all settings
            self.external_ids = Some(HashMap::new());
            self.other_config = Some(HashMap::new());
            return;
        }

        if self.prop_list.contains(&"external_ids") {
            if let Some(external_ids) = self.external_ids.as_mut() {
                if !external_ids.is_empty() {
                    merge_hashmap(external_ids, current.external_ids.as_ref());
                }
            } else {
                self.external_ids = current.external_ids.clone();
            }
        } else {
            self.external_ids = current.external_ids.clone();
        }

        if self.prop_list.contains(&"other_config") {
            if let Some(other_config) = self.other_config.as_mut() {
                if !other_config.is_empty() {
                    merge_hashmap(other_config, current.other_config.as_ref());
                }
            } else {
                self.other_config = current.other_config.clone();
            }
        } else {
            self.other_config = current.other_config.clone();
        }
    }

    pub(crate) fn get_other_config(&self) -> HashMap<&str, &str> {
        let mut ret = HashMap::new();
        if let Some(ocfg) = self.other_config.as_ref() {
            for (k, v) in ocfg.iter() {
                if let Some(v) = v {
                    ret.insert(k.as_str(), v.as_str());
                }
            }
        }
        ret
    }

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
}

fn merge_hashmap(
    desired: &mut HashMap<String, Option<String>>,
    current: Option<&HashMap<String, Option<String>>>,
) {
    if let Some(current) = current {
        for (key, value) in current.iter() {
            if !desired.contains_key(key) {
                desired.insert(key.clone(), value.clone());
            }
        }
    }
    desired.retain(|_, v| !v.is_none());
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

    pub(crate) fn pre_verify_cleanup(&mut self) {
        // User desired empty port list, but OVS bridge cannot exist without a
        // port, as ovs-vsctl did, we create a internal interface with the same
        // name as bridge
        if self.ports().map(|p| p.is_empty()) == Some(true) {
            if let Some(br_conf) = &mut self.bridge {
                br_conf.ports = Some(vec![OvsBridgePortConfig {
                    name: self.base.name.clone(),
                    ..Default::default()
                }])
            }
        }
        self.sort_ports()
    }

    fn sort_ports(&mut self) {
        if let Some(ref mut br_conf) = self.bridge {
            if let Some(ref mut port_confs) = &mut br_conf.ports {
                port_confs.sort_unstable_by_key(|p| p.name.clone());
                for port_conf in port_confs {
                    if let Some(ref mut bond_conf) = port_conf.bond {
                        bond_conf.sort_ports();
                    }
                }
            }
        }
    }

    // Only support remove non-bonding port or the bond itself as bond require
    // two ports, removal any of them will trigger error.
    pub(crate) fn remove_port(&mut self, port_name: &str) {
        if let Some(br_ports) = self
            .bridge
            .as_mut()
            .and_then(|br_conf| br_conf.ports.as_mut())
        {
            br_ports.retain(|p| p.name.as_str() != port_name)
        }
    }

    pub(crate) fn change_port_name(
        &mut self,
        origin_name: &str,
        new_name: String,
    ) {
        if let Some(index) = self
            .bridge
            .as_ref()
            .and_then(|br_conf| br_conf.ports.as_ref())
            .and_then(|ports| {
                ports.iter().position(|port| port.name == origin_name)
            })
        {
            if let Some(ports) = self
                .bridge
                .as_mut()
                .and_then(|br_conf| br_conf.ports.as_mut())
            {
                ports[index].name = new_name;
            }
        } else if let Some(index) = self
            .bridge
            .as_ref()
            .and_then(|br_conf| br_conf.ports.as_ref())
            .and_then(|ports| {
                ports.iter().position(|port_conf| {
                    port_conf
                        .bond
                        .as_ref()
                        .and_then(|bond_conf| bond_conf.ports.as_ref())
                        .map(|bond_port_confs| {
                            bond_port_confs
                                .iter()
                                .any(|bond_conf| bond_conf.name == origin_name)
                        })
                        .unwrap_or_default()
                })
            })
        {
            if let Some(bond_port_confs) = self
                .bridge
                .as_mut()
                .and_then(|br_conf| br_conf.ports.as_mut())
                .and_then(|ports| ports.get_mut(index))
                .and_then(|port_conf| port_conf.bond.as_mut())
                .and_then(|bond_conf| bond_conf.ports.as_mut())
            {
                for bond_port_conf in bond_port_confs {
                    if bond_port_conf.name == origin_name {
                        bond_port_conf.name = new_name;
                        break;
                    }
                }
            }
        }
    }
}

impl OvsBridgeBondConfig {
    pub(crate) fn sort_ports(&mut self) {
        if let Some(ref mut bond_ports) = self.ports {
            bond_ports.sort_unstable_by_key(|p| p.name.clone())
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
