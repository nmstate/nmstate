// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use crate::{MergedInterfaces, NmstateFeature};

impl MergedInterfaces {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        let mut ret: HashSet<NmstateFeature> = HashSet::new();
        for iface in self
            .kernel_ifaces
            .values()
            .chain(self.user_ifaces.values())
            .filter(|i| i.is_desired() || i.is_changed())
        {
            for feature in iface.get_features() {
                ret.insert(feature);
            }
        }
        ret.drain().collect()
    }
}
