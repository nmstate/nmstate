// SPDX-License-Identifier: Apache-2.0

use crate::{BridgePortTunkTag, BridgePortVlanConfig};

impl BridgePortVlanConfig {
    pub(crate) fn flatten_vlan_ranges(&mut self) {
        if let Some(trunk_tags) = &self.trunk_tags {
            let mut new_trunk_tags = Vec::new();
            for trunk_tag in trunk_tags {
                match trunk_tag {
                    BridgePortTunkTag::Id(_) => {
                        new_trunk_tags.push(trunk_tag.clone())
                    }
                    BridgePortTunkTag::IdRange(range) => {
                        for i in range.min..range.max + 1 {
                            new_trunk_tags.push(BridgePortTunkTag::Id(i));
                        }
                    }
                };
            }
            self.trunk_tags = Some(new_trunk_tags);
        }
    }

    pub(crate) fn sort_trunk_tags(&mut self) {
        if let Some(trunk_tags) = self.trunk_tags.as_mut() {
            trunk_tags.sort_unstable_by(|tag_a, tag_b| match (tag_a, tag_b) {
                (BridgePortTunkTag::Id(a), BridgePortTunkTag::Id(b)) => {
                    a.cmp(b)
                }
                _ => {
                    log::warn!(
                        "Please call flatten_vlan_ranges() \
                        before sort_port_vlans()"
                    );
                    std::cmp::Ordering::Equal
                }
            })
        }
    }
}
