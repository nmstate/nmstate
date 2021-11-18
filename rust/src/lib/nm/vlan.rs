use crate::VlanConfig;
use nm_dbus::NmSettingVlan;

impl From<&VlanConfig> for NmSettingVlan {
    fn from(config: &VlanConfig) -> Self {
        let mut settings = NmSettingVlan::new();
        settings.id = Some(config.id.into());
        settings.parent = Some(config.base_iface.clone());
        settings
    }
}
