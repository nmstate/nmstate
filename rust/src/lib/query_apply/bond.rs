// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{
    BondConfig, BondInterface, BondOptions, Interface, MergedInterface,
};

impl BondInterface {
    pub(crate) fn update_bond(&mut self, other: &BondInterface) {
        if let Some(bond_conf) = &mut self.bond {
            bond_conf.update(other.bond.as_ref());
        } else {
            self.bond.clone_from(&other.bond);
        }
    }
}

impl BondConfig {
    pub(crate) fn update(&mut self, other: Option<&BondConfig>) {
        if let Some(other) = other {
            if let Some(mode) = other.mode {
                self.mode = Some(mode);
            }
            if let Some(self_opts) = self.options.as_mut() {
                self_opts.update(other.options.as_ref());
            } else {
                self.options.clone_from(&other.options);
            }
            if let Some(port) = other.port.as_ref() {
                self.port = Some(port.clone());
            }
        }
    }
}

impl BondOptions {
    // Only allow update `balance_slb` as that is userspace value.
    // Other options should be provided by nispor via kernel netlink.
    pub(crate) fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            if let Some(value) = other.balance_slb {
                self.balance_slb = Some(value);
            }
        }
    }
}

impl MergedInterface {
    pub(crate) fn get_bond_ports_with_queue_id_changed(&self) -> Vec<&str> {
        let mut ret: Vec<&str> = Vec::new();
        let mut des_queue_ids: HashMap<&str, u16> = HashMap::new();
        let mut cur_queue_ids: HashMap<&str, u16> = HashMap::new();

        if let Some(Interface::Bond(des_iface)) = self.desired.as_ref() {
            if let Some(port_confs) = des_iface
                .bond
                .as_ref()
                .and_then(|b| b.ports_config.as_ref())
            {
                for port_conf in port_confs
                    .iter()
                    .filter(|p| p.queue_id.is_some() && p.queue_id != Some(0))
                {
                    des_queue_ids.insert(
                        port_conf.name.as_str(),
                        port_conf.queue_id.unwrap_or_default(),
                    );
                }
            }
        }

        if let Some(Interface::Bond(cur_iface)) = self.current.as_ref() {
            if let Some(port_confs) = cur_iface
                .bond
                .as_ref()
                .and_then(|b| b.ports_config.as_ref())
            {
                for port_conf in port_confs
                    .iter()
                    .filter(|p| p.queue_id.is_some() && p.queue_id != Some(0))
                {
                    cur_queue_ids.insert(
                        port_conf.name.as_str(),
                        port_conf.queue_id.unwrap_or_default(),
                    );
                }
            }
        }

        // Find desired bond port with changed queue id
        for (des_iface_name, des_queue_id) in des_queue_ids.iter() {
            if cur_queue_ids.get(des_iface_name) != Some(des_queue_id) {
                ret.push(des_iface_name);
            }
        }

        // Find current port holds queue_id but desired bond port removed or
        // unset queue_id
        for (cur_iface_name, cur_queue_id) in cur_queue_ids.iter() {
            if des_queue_ids.get(cur_iface_name) != Some(cur_queue_id) {
                ret.push(cur_iface_name);
            }
        }
        ret
    }
}
