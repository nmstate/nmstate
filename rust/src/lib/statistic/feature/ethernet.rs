// SPDX-License-Identifier: Apache-2.0

use crate::{EthernetInterface, NmstateFeature};

impl EthernetInterface {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        if self.ethernet.as_ref().map(|e| e.sr_iov.is_some()) == Some(true) {
            vec![NmstateFeature::Sriov]
        } else {
            Vec::new()
        }
    }
}
