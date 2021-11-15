use crate::{ErrorKind, InterfaceIpv4, InterfaceIpv6, NmstateError};
use nm_dbus::{NmSettingIp, NmSettingIpMethod};

pub(crate) fn iface_ipv4_to_nm(
    iface_ip: &InterfaceIpv4,
) -> Result<NmSettingIp, NmstateError> {
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
    let mut nm_setting = NmSettingIp::new();
    nm_setting.method = Some(method);
    nm_setting.addresses = addresses;
    Ok(nm_setting)
}

pub(crate) fn iface_ipv6_to_nm(
    iface_ip: &InterfaceIpv6,
) -> Result<NmSettingIp, NmstateError> {
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
    let mut nm_setting = NmSettingIp::new();
    nm_setting.method = Some(method);
    nm_setting.addresses = addresses;
    Ok(nm_setting)
}
