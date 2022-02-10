use std::ops::BitXor;

use crate::{
    nm::dns::{apply_nm_dns_setting, nm_dns_to_nmstate},
    nm::route::gen_nm_ip_routes,
    nm::route_rule::gen_nm_ip_rules,
    ErrorKind, Interface, InterfaceIpv4, InterfaceIpv6, NmstateError,
    RouteEntry, RouteRuleEntry,
};
use nm_dbus::{NmConnection, NmSettingIp, NmSettingIpMethod};

const NM_CONFIG_ADDR_GEN_MODE_EUI64: i32 = 0;

fn gen_nm_ipv4_setting(
    iface_ip: Option<&InterfaceIpv4>,
    routes: Option<&[RouteEntry]>,
    rules: Option<&[RouteRuleEntry]>,
    nm_conn: &mut NmConnection,
) -> Result<(), NmstateError> {
    let iface_ip = match iface_ip {
        None => {
            if nm_conn.ipv4.is_none() {
                let mut nm_setting = NmSettingIp::default();
                nm_setting.method = Some(NmSettingIpMethod::Disabled);
                nm_conn.ipv4 = Some(nm_setting);
            }
            return Ok(());
        }
        Some(i) => i,
    };

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
    if iface_ip.enabled && iface_ip.dhcp {
        nm_setting.dhcp_timeout = Some(i32::MAX);
        nm_setting.dhcp_client_id = Some("mac".to_string());
        apply_dhcp_opts(
            &mut nm_setting,
            iface_ip.auto_dns,
            iface_ip.auto_gateway,
            iface_ip.auto_routes,
            iface_ip.auto_table_id,
        );
        // No use case indicate we should support static routes with DHCP
        // enabled.
        nm_setting.routes = Vec::new();
    }
    if iface_ip.enabled && !iface_ip.dhcp {
        if let Some(routes) = routes {
            nm_setting.routes = gen_nm_ip_routes(routes, false)?;
            // We use above routes property for gateway also, in order
            // to support multiple gateways.
            nm_setting.gateway = None;
        }
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
    iface_ip: Option<&InterfaceIpv6>,
    routes: Option<&[RouteEntry]>,
    rules: Option<&[RouteRuleEntry]>,
    nm_conn: &mut NmConnection,
) -> Result<(), NmstateError> {
    let iface_ip = match iface_ip {
        None => {
            if nm_conn.ipv6.is_none() {
                let mut nm_setting = NmSettingIp::default();
                nm_setting.method = Some(NmSettingIpMethod::Disabled);
                nm_conn.ipv6 = Some(nm_setting);
            }
            return Ok(());
        }
        Some(i) => i,
    };
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
    if iface_ip.enabled && (iface_ip.dhcp || iface_ip.autoconf) {
        nm_setting.dhcp_timeout = Some(i32::MAX);
        nm_setting.ra_timeout = Some(i32::MAX);
        nm_setting.addr_gen_mode = Some(NM_CONFIG_ADDR_GEN_MODE_EUI64);
        nm_setting.dhcp_duid = Some("ll".to_string());
        nm_setting.dhcp_iaid = Some("mac".to_string());
        apply_dhcp_opts(
            &mut nm_setting,
            iface_ip.auto_dns,
            iface_ip.auto_gateway,
            iface_ip.auto_routes,
            iface_ip.auto_table_id,
        );
        // No use case indicate we should support static routes with DHCP
        // enabled.
        nm_setting.routes = Vec::new();
    }
    if iface_ip.enabled && !iface_ip.dhcp && !iface_ip.autoconf {
        if let Some(routes) = routes {
            nm_setting.routes = gen_nm_ip_routes(routes, true)?;
        }
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
        gen_nm_ipv4_setting(base_iface.ipv4.as_ref(), routes, rules, nm_conn)?;
        gen_nm_ipv6_setting(base_iface.ipv6.as_ref(), routes, rules, nm_conn)?;
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
        let (auto_dns, auto_gateway, auto_routes, auto_table_id) =
            parse_dhcp_opts(nm_ip_setting);
        InterfaceIpv4 {
            enabled,
            dhcp,
            auto_dns,
            auto_routes,
            auto_gateway,
            auto_table_id,
            prop_list: vec![
                "enabled",
                "dhcp",
                "dns",
                "auto_dns",
                "auto_routes",
                "auto_gateway",
                "auto_table_id",
            ],
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
            _ => {
                log::warn!("Unknown NM IP method {:?}", nm_ip_method);
                (false, false, false)
            }
        };
        let (auto_dns, auto_gateway, auto_routes, auto_table_id) =
            parse_dhcp_opts(nm_ip_setting);
        InterfaceIpv6 {
            enabled,
            dhcp,
            autoconf,
            auto_dns,
            auto_routes,
            auto_gateway,
            auto_table_id,
            prop_list: vec![
                "enabled",
                "dhcp",
                "autoconf",
                "dns",
                "auto_dns",
                "auto_routes",
                "auto_gateway",
                "auto_table_id",
            ],
            dns: Some(nm_dns_to_nmstate(nm_ip_setting)),
            ..Default::default()
        }
    } else {
        InterfaceIpv6::default()
    }
}

// return (auto_dns, auto_gateway, auto_routes, auto_table_id)
fn parse_dhcp_opts(
    nm_setting: &NmSettingIp,
) -> (Option<bool>, Option<bool>, Option<bool>, Option<u32>) {
    (
        Some(nm_setting.ignore_auto_dns.map(flip_bool).unwrap_or(true)),
        Some(nm_setting.never_default.map(flip_bool).unwrap_or(true)),
        Some(nm_setting.ignore_auto_routes.map(flip_bool).unwrap_or(true)),
        Some(nm_setting.route_table.unwrap_or_default()),
    )
}

fn apply_dhcp_opts(
    nm_setting: &mut NmSettingIp,
    auto_dns: Option<bool>,
    auto_gateway: Option<bool>,
    auto_routes: Option<bool>,
    auto_table_id: Option<u32>,
) {
    if let Some(v) = auto_dns {
        nm_setting.ignore_auto_dns = Some(flip_bool(v));
    }
    if let Some(v) = auto_gateway {
        nm_setting.never_default = Some(flip_bool(v));
    }
    if let Some(v) = auto_routes {
        nm_setting.ignore_auto_routes = Some(flip_bool(v));
    }
    if let Some(v) = auto_table_id {
        nm_setting.route_table = Some(v);
    }
}

fn flip_bool(v: bool) -> bool {
    v.bitxor(true)
}
