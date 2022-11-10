// SPDX-License-Identifier: Apache-2.0

use crate::{BondConfig, BondInterface, BondOptions};

impl BondInterface {
    pub(crate) fn update_bond(&mut self, other: &BondInterface) {
        if let Some(bond_conf) = &mut self.bond {
            bond_conf.update(other.bond.as_ref());
        } else {
            self.bond = other.bond.clone();
        }
    }

    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.drop_empty_arp_ip_target();
        self.sort_ports();
    }

    fn drop_empty_arp_ip_target(&mut self) {
        if let Some(ref mut bond_conf) = self.bond {
            if let Some(ref mut bond_opts) = &mut bond_conf.options {
                if let Some(ref mut arp_ip_target) = bond_opts.arp_ip_target {
                    if arp_ip_target.is_empty() {
                        bond_opts.arp_ip_target = None;
                    }
                }
            }
        }
    }

    fn sort_ports(&mut self) {
        if let Some(ref mut bond_conf) = self.bond {
            if let Some(ref mut port_conf) = &mut bond_conf.port {
                port_conf.sort_unstable_by_key(|p| p.clone())
            }
        }
    }

    pub(crate) fn remove_port(&mut self, port_to_remove: &str) {
        if let Some(index) = self.bond.as_ref().and_then(|bond_conf| {
            bond_conf.port.as_ref().and_then(|ports| {
                ports
                    .iter()
                    .position(|port_name| port_name == port_to_remove)
            })
        }) {
            self.bond
                .as_mut()
                .and_then(|bond_conf| bond_conf.port.as_mut())
                .map(|ports| ports.remove(index));
        }
    }

    pub(crate) fn change_port_name(
        &mut self,
        origin_name: &str,
        new_name: String,
    ) {
        if let Some(index) = self
            .bond
            .as_ref()
            .and_then(|bond_conf| bond_conf.port.as_ref())
            .and_then(|ports| {
                ports.iter().position(|port_name| port_name == origin_name)
            })
        {
            if let Some(ports) = self
                .bond
                .as_mut()
                .and_then(|bond_conf| bond_conf.port.as_mut())
            {
                ports[index] = new_name;
            }
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
                self.options = other.options.clone();
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
