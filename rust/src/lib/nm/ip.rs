use crate::{
    nm::dns::{apply_nm_dns_setting, nm_dns_to_nmstate},
    nm::route::gen_nm_ip_routes,
    nm::route_rule::gen_nm_ip_rules,
    ErrorKind, Interface, InterfaceIpv4, InterfaceIpv6, NmstateError,
    RouteEntry, RouteRuleEntry,
};
use nm_dbus::{NmConnection, NmSettingIp, NmSettingIpMethod};

fn gen_nm_ipv4_setting(
    iface_ip: &InterfaceIpv4,
    routes: Option<&[RouteEntry]>,
    rules: Option<&[RouteRuleEntry]>,
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
    if let Some(routes) = routes {
        nm_setting.routes = gen_nm_ip_routes(routes, false)?;
    }
    if let Some(rules) = rules {
        nm_setting.route_rules = gen_nm_ip_rules(rules, false)?;
    }
    if let Some(dns) = &iface_ip.dns {
        apply_nm_dns_setting(&mut nm_setting, dns);
    }
    nm_conn.ipv4 = Some(nm_setting);
    Ok(())
}

fn gen_nm_ipv6_setting(
    iface_ip: &InterfaceIpv6,
    routes: Option<&[RouteEntry]>,
    rules: Option<&[RouteRuleEntry]>,
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
    if let Some(routes) = routes {
        nm_setting.routes = gen_nm_ip_routes(routes, true)?;
    }
    if let Some(rules) = rules {
        nm_setting.route_rules = gen_nm_ip_rules(rules, true)?;
    }
    if let Some(dns) = &iface_ip.dns {
        apply_nm_dns_setting(&mut nm_setting, dns);
    }
    nm_conn.ipv6 = Some(nm_setting);
    Ok(())
}

pub(crate) fn gen_nm_ip_setting(
    iface: &Interface,
    routes: Option<&[RouteEntry]>,
    rules: Option<&[RouteRuleEntry]>,
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
        gen_nm_ipv4_setting(&ipv4_conf, routes, rules, nm_conn)?;
        gen_nm_ipv6_setting(&ipv6_conf, routes, rules, nm_conn)?;
    } else {
        nm_conn.ipv4 = None;
        nm_conn.ipv6 = None;
    }
    Ok(())
}

pub(crate) fn nm_ip_setting_to_nmstate4(
    nm_ip_setting: &NmSettingIp,
) -> InterfaceIpv4 {
    if let Some(nm_ip_method) = &nm_ip_setting.method {
        let (enabled, dhcp) = match nm_ip_method {
            NmSettingIpMethod::Disabled => (false, false),
            NmSettingIpMethod::LinkLocal
            | NmSettingIpMethod::Manual
            | NmSettingIpMethod::Shared => (true, false),
            NmSettingIpMethod::Auto => (true, true),
            _ => {
                log::warn!("Unexpected NM IP method {:?}", nm_ip_method);
                (true, false)
            }
        };
        InterfaceIpv4 {
            enabled,
            dhcp,
            prop_list: vec!["enabled", "dhcp", "dns"],
            dns: Some(nm_dns_to_nmstate(nm_ip_setting)),
            ..Default::default()
        }
    } else {
        InterfaceIpv4::default()
    }
}

pub(crate) fn nm_ip_setting_to_nmstate6(
    nm_ip_setting: &NmSettingIp,
) -> InterfaceIpv6 {
    if let Some(nm_ip_method) = &nm_ip_setting.method {
        let (enabled, dhcp, autoconf) = match nm_ip_method {
            NmSettingIpMethod::Disabled => (false, false, false),
            NmSettingIpMethod::LinkLocal
            | NmSettingIpMethod::Manual
            | NmSettingIpMethod::Shared => (true, false, false),
            NmSettingIpMethod::Auto => (true, true, true),
            NmSettingIpMethod::Dhcp => (true, true, false),
            NmSettingIpMethod::Ignore => (true, false, false),
        };
        InterfaceIpv6 {
            enabled,
            dhcp,
            autoconf,
            prop_list: vec!["enabled", "dhcp", "autoconf", "dns"],
            dns: Some(nm_dns_to_nmstate(nm_ip_setting)),
            ..Default::default()
        }
    } else {
        InterfaceIpv6::default()
    }
}
