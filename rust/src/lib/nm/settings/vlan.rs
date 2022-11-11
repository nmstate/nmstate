// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmSettingVlan;

use crate::VlanConfig;

impl From<&VlanConfig> for NmSettingVlan {
    fn from(config: &VlanConfig) -> Self {
        let mut settings = NmSettingVlan::default();
        settings.id = Some(config.id.into());
        settings.parent = Some(config.base_iface.clone());
        settings
    }
}
