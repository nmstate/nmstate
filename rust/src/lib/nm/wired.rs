use crate::nm::version::nm_supports_accept_all_mac_addresses_mode;
use crate::Interface;
use nm_dbus::NmConnection;

pub(crate) fn gen_nm_wired_setting(
    iface: &Interface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_wired_set = nm_conn.wired.as_ref().cloned().unwrap_or_default();

    let mut flag_need_wired = false;

    let base_iface = iface.base_iface();

    if let Some(mac) = &base_iface.mac_address {
        nm_wired_set.cloned_mac_address = Some(mac.to_string());
        flag_need_wired = true;
    }
    if let Some(mtu) = &base_iface.mtu {
        nm_wired_set.mtu = Some(*mtu as u32);
        flag_need_wired = true;
    }
    if let Some(accept_all_mac_addresses) = &base_iface.accept_all_mac_addresses
    {
        if nm_supports_accept_all_mac_addresses_mode().unwrap_or_default() {
            nm_wired_set.accept_all_mac_addresses =
                Some(i32::from(*accept_all_mac_addresses));
            flag_need_wired = true;
        }
    }

    if flag_need_wired {
        nm_conn.wired = Some(nm_wired_set);
    }
}
