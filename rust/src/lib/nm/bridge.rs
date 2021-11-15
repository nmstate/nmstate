use crate::{LinuxBridgeConfig, NmstateError};
use nm_dbus::NmSettingBridge;

pub(crate) fn linux_bridge_conf_to_nm(
    br_conf: &LinuxBridgeConfig,
) -> Result<NmSettingBridge, NmstateError> {
    let mut nm_setting = NmSettingBridge::new();
    if let Some(stp_enabled) = br_conf
        .options
        .as_ref()
        .and_then(|br_opts| br_opts.stp.as_ref())
        .and_then(|stp_opts| stp_opts.enabled)
    {
        nm_setting.stp = Some(stp_enabled);
    }
    Ok(nm_setting)
}
