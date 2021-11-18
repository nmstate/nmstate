use crate::{ErrorKind, Interface, InterfaceIpv4, InterfaceIpv6, NmstateError};
use nm_dbus::{NmConnection, NmSettingIpMethod};

fn gen_nm_ipv4_setting(
    iface_ip: &InterfaceIpv4,
    nm_conn: &mut NmConnection,
) -> Result<(), NmstateError> {
    let mut addresses: Vec<String> = Vec::new();
    let method = if iface_ip.enabled {
        if iface_ip.dhcp {
            NmSettingIpMethod::Auto
        } else if !iface_ip.addresses.is_empty() {
            for ip_addr in &iface_ip.addresses {
                addresses
                    .push(format!("{}/{}", ip_addr.ip, ip_addr.prefix_length));
            }
            NmSettingIpMethod::Manual
        } else {
            NmSettingIpMethod::Disabled
        }
    } else {
        NmSettingIpMethod::Disabled
    };

    let mut nm_setting = nm_conn.ipv4.as_ref().cloned().unwrap_or_default();
    nm_setting.method = Some(method);
    nm_setting.addresses = addresses;
    nm_conn.ipv4 = Some(nm_setting);
    Ok(())
}

fn gen_nm_ipv6_setting(
    iface_ip: &InterfaceIpv6,
    nm_conn: &mut NmConnection,
) -> Result<(), NmstateError> {
    let mut addresses: Vec<String> = Vec::new();
    let method = if iface_ip.enabled {
        match (iface_ip.dhcp, iface_ip.autoconf) {
            (true, true) => NmSettingIpMethod::Auto,
            (true, false) => NmSettingIpMethod::Dhcp,
            (false, true) => {
                return Err(NmstateError::new(
                    ErrorKind::NotImplementedError,
                    "Autoconf without DHCP is not supported yet".to_string(),
                ))
            }
            (false, false) => {
                if !iface_ip.addresses.is_empty() {
                    for ip_addr in &iface_ip.addresses {
                        addresses.push(format!(
                            "{}/{}",
                            ip_addr.ip, ip_addr.prefix_length
                        ));
                    }
                    NmSettingIpMethod::Manual
                } else {
                    NmSettingIpMethod::LinkLocal
                }
            }
        }
    } else {
        NmSettingIpMethod::Disabled
    };
    let mut nm_setting = nm_conn.ipv6.as_ref().cloned().unwrap_or_default();
    nm_setting.method = Some(method);
    nm_setting.addresses = addresses;
    nm_conn.ipv6 = Some(nm_setting);
    Ok(())
}

pub(crate) fn gen_nm_ip_setting(
    iface: &Interface,
    nm_conn: &mut NmConnection,
) -> Result<(), NmstateError> {
    let base_iface = iface.base_iface();
    if base_iface.can_have_ip() {
        let ipv4_conf = if let Some(ipv4_conf) = &base_iface.ipv4 {
            ipv4_conf.clone()
        } else {
            let mut ipv4_conf = InterfaceIpv4::new();
            ipv4_conf.enabled = false;
            ipv4_conf
        };
        let ipv6_conf = if let Some(ipv6_conf) = &base_iface.ipv6 {
            ipv6_conf.clone()
        } else {
            let mut ipv6_conf = InterfaceIpv6::new();
            ipv6_conf.enabled = false;
            ipv6_conf
        };
        gen_nm_ipv4_setting(&ipv4_conf, nm_conn)?;
        gen_nm_ipv6_setting(&ipv6_conf, nm_conn)?;
    } else {
        nm_conn.ipv4 = None;
        nm_conn.ipv6 = None;
    }
    Ok(())
}
