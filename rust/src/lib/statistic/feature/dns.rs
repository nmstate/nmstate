// SPDX-License-Identifier: Apache-2.0

use crate::{MergedDnsState, NmstateFeature};

impl MergedDnsState {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        let mut ret = Vec::new();
        if let Some(dns_config) = self.desired.config.as_ref() {
            if dns_config.server.is_some() {
                ret.push(NmstateFeature::StaticDnsNameServer);
            }
            if dns_config.search.is_some() {
                ret.push(NmstateFeature::StaticDnsSearch);
            }
            if dns_config.options.is_some() {
                ret.push(NmstateFeature::StaticDnsOption);
            }
        }
        ret
    }
}
