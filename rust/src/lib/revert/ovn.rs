// SPDX-License-Identifier: Apache-2.0

use crate::{
    MergedOvnConfiguration, OvnBridgeMapping, OvnBridgeMappingState,
    OvnConfiguration,
};

impl MergedOvnConfiguration {
    pub(crate) fn generate_revert(&self) -> OvnConfiguration {
        let mut revert_maps: Vec<OvnBridgeMapping> = Vec::new();

        let empty_vev: Vec<OvnBridgeMapping> = Vec::new();

        for des_map in
            self.desired.bridge_mappings.as_ref().unwrap_or(&empty_vev)
        {
            let mut found_match = false;
            for cur_map in
                self.current.bridge_mappings.as_ref().unwrap_or(&empty_vev)
            {
                if des_map.localnet.as_str() == cur_map.localnet.as_str() {
                    found_match = true;
                    revert_maps.push(cur_map.clone());
                }
            }
            if !found_match {
                let mut map = des_map.clone();
                map.state = Some(OvnBridgeMappingState::Absent);
                map.bridge = None;
                revert_maps.push(map);
            }
        }

        revert_maps.sort_unstable();

        if revert_maps.is_empty() {
            OvnConfiguration::default()
        } else {
            OvnConfiguration {
                bridge_mappings: Some(revert_maps),
            }
        }
    }
}
