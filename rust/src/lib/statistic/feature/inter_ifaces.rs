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

        let iface_count = self
            .kernel_ifaces
            .values()
            .chain(self.user_ifaces.values())
            .filter(|i| i.merged.is_up() && (i.is_desired()))
            .count();
        if iface_count >= 500 {
            ret.insert(NmstateFeature::IfaceCount500Plus);
        } else if iface_count >= 200 {
            ret.insert(NmstateFeature::IfaceCount200Plus);
        } else if iface_count >= 100 {
            ret.insert(NmstateFeature::IfaceCount100Plus);
        } else if iface_count >= 50 {
            ret.insert(NmstateFeature::IfaceCount50Plus);
        } else if iface_count >= 10 {
            ret.insert(NmstateFeature::IfaceCount10Plus);
        }

        ret.drain().collect()
    }
}
