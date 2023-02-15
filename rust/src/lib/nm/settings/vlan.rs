// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmSettingVlan;

use crate::{VlanConfig, VlanProtocol};

impl From<&VlanConfig> for NmSettingVlan {
    fn from(config: &VlanConfig) -> Self {
        let mut settings = NmSettingVlan::default();
        settings.id = Some(config.id.into());
        settings.parent = Some(config.base_iface.clone());
        // To support old NetworkManager 1.41- which VLAN protocol is not
        // supported, we only set non-default protocol(802.1ad)
        if Some(VlanProtocol::Ieee8021Ad) == config.protocol {
            settings.protocol = Some("802.1ad".to_string());
        }
        settings
    }
}
