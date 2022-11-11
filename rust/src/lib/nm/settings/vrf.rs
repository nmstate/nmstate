// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmSettingVrf;

use crate::VrfConfig;

impl From<&VrfConfig> for NmSettingVrf {
    fn from(config: &VrfConfig) -> Self {
        let mut settings = NmSettingVrf::default();
        settings.table = Some(config.table_id);
        settings
    }
}
