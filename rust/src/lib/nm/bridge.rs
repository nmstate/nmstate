use crate::LinuxBridgeInterface;
use nm_dbus::NmConnection;

pub(crate) fn gen_nm_br_setting(
    br_iface: &LinuxBridgeInterface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_br_set = nm_conn.bridge.as_ref().cloned().unwrap_or_default();

    if let Some(stp_enabled) = br_iface
        .bridge
        .as_ref()
        .and_then(|br_conf| br_conf.options.as_ref())
        .and_then(|br_opts| br_opts.stp.as_ref())
        .and_then(|stp_opts| stp_opts.enabled)
    {
        nm_br_set.stp = Some(stp_enabled);
    }
    nm_conn.bridge = Some(nm_br_set);
}
