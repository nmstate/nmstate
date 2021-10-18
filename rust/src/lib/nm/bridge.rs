use crate::{
    LinuxBridgeConfig, LinuxBridgeOptions, LinuxBridgeStpOptions, NmstateError,
};
use nm_dbus::NmSettingBridge;

pub(crate) fn linux_bridge_conf_to_nm(
    br_conf: &LinuxBridgeConfig,
) -> Result<NmSettingBridge, NmstateError> {
    if let Some(LinuxBridgeOptions {
        stp:
            Some(LinuxBridgeStpOptions {
                enabled: stp_enabled,
                ..
            }),
        ..
    }) = br_conf.options
    {
        return Ok(NmSettingBridge { stp: stp_enabled });
    }
    Ok(NmSettingBridge::default())
}
