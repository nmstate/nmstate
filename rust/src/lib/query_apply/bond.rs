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
