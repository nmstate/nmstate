// SPDX-License-Identifier: Apache-2.0

use crate::{InterfaceIpv4, InterfaceIpv6, NmstateFeature};

impl InterfaceIpv4 {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        if self.dhcp_custom_hostname.is_some() {
            vec![NmstateFeature::Dhcpv4CustomHostname]
        } else {
            Vec::new()
        }
    }
}

impl InterfaceIpv6 {
    pub(crate) fn get_features(&self) -> Vec<NmstateFeature> {
        if self.dhcp_custom_hostname.is_some() {
            vec![NmstateFeature::Dhcpv6CustomHostname]
        } else {
            Vec::new()
        }
    }
}
