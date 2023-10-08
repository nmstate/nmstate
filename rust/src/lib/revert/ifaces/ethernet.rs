// SPDX-License-Identifier: Apache-2.0

use crate::{EthernetConfig, EthernetInterface, Interface, SrIovConfig};

impl EthernetInterface {
    pub(crate) fn generate_revert_extra(
        &mut self,
        desired: &Interface,
        current: &Interface,
    ) {
        if let (Interface::Ethernet(desired), Interface::Ethernet(current)) =
            (desired, current)
        {
            if desired.sriov_is_enabled() && !current.sriov_is_enabled() {
                self.ethernet
                    .get_or_insert(EthernetConfig::new())
                    .sr_iov
                    .get_or_insert(SrIovConfig {
                        total_vfs: Some(0),
                        ..Default::default()
                    });
            }
        }
    }
}
