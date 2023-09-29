// SPDX-License-Identifier: Apache-2.0

use crate::{
    MergedOvnConfiguration, MergedOvsDbGlobalConfig, NmstateFeature,
    OvsBridgeInterface, OvsDbIfaceConfig, OvsInterface,
};

impl MergedOvsDbGlobalConfig {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        if !self.desired.is_none() {
            vec![NmstateFeature::OvsDbGlobal]
        } else {
            Vec::new()
        }
    }
}

impl MergedOvnConfiguration {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        if !self.desired.is_none() {
            vec![NmstateFeature::OvnMapping]
        } else {
            Vec::new()
        }
    }
}

impl OvsDbIfaceConfig {
    pub(crate) fn is_empty(&self) -> bool {
        self.get_external_ids().is_empty() && self.get_other_config().is_empty()
    }
}

impl OvsBridgeInterface {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        let mut ret = Vec::new();
        if let Some(ports) =
            self.bridge.as_ref().and_then(|b| b.ports.as_deref())
        {
            if ports.iter().any(|p| p.bond.is_some()) {
                ret.push(NmstateFeature::OvsBond);
            }
        }
        ret
    }
}

impl OvsInterface {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        let mut ret = Vec::new();
        if self.dpdk.is_some() {
            ret.push(NmstateFeature::OvsDpdk);
        }
        ret
    }
}
