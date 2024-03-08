// SPDX-License-Identifier: Apache-2.0

use crate::IpsecInterface;

impl IpsecInterface {
    pub(crate) fn update_ipsec(&mut self, other: &Self) {
        // Always override
        self.libreswan.clone_from(&other.libreswan);
    }
}
