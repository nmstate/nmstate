// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmSettingVxlan;

use crate::VxlanConfig;

impl From<&VxlanConfig> for NmSettingVxlan {
    fn from(config: &VxlanConfig) -> Self {
        let mut setting = NmSettingVxlan::default();
        setting.id = Some(config.id);
        if !config.base_iface.is_empty() {
            setting.parent = Some(config.base_iface.clone());
        }
        if let Some(v) = config.learning {
            setting.learning = Some(v);
        }
        if let Some(v) = config.local.as_ref() {
            setting.local = Some(v.to_string());
        }
        if let Some(v) = config.remote.as_ref() {
            setting.remote = Some(v.to_string());
        }
        if let Some(v) = config.dst_port {
            setting.dst_port = Some(v.into())
        }
        setting
    }
}
