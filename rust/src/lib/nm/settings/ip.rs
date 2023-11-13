// SPDX-License-Identifier: Apache-2.0

use std::ops::BitXor;

use super::{
    dns::apply_nm_dns_setting, route::gen_nm_ip_routes,
    route_rule::gen_nm_ip_rules,
};
use crate::nm::nm_dbus::{NmConnection, NmSettingIp, NmSettingIpMethod};
use crate::{
    BaseInterface, Dhcpv4ClientId, Dhcpv6Duid, ErrorKind, Interface,
    InterfaceIpAddr, InterfaceIpv4, InterfaceIpv6, Ipv6AddrGenMode,
    NmstateError, RouteEntry, WaitIp,
};

const ADDR_GEN_MODE_EUI64: i32 = 0;
const ADDR_GEN_MODE_STABLE_PRIVACY: i32 = 1;

fn gen_nm_ipv4_setting(
    iface_ip: Option<&InterfaceIpv4>,
    routes: Option<&[RouteEntry]>,
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

    let nmstate_ip_addrs: Vec<InterfaceIpAddr> = iface_ip
        .addresses
        .as_deref()
        .unwrap_or_default()
        .iter()
        .filter(|i| !i.is_auto())
        .cloned()
        .collect();

    let mut addresses: Vec<String> = Vec::new();
    let method = if iface_ip.enabled {
        if iface_ip.dhcp == Some(true) {
            NmSettingIpMethod::Auto
        } else if !nmstate_ip_addrs.is_empty() {
            NmSettingIpMethod::Manual
        } else {
            NmSettingIpMethod::Disabled
        }
    } else {
        NmSettingIpMethod::Disabled
    };
    for ip_addr in nmstate_ip_addrs {
        addresses.push(format!("{}/{}", ip_addr.ip, ip_addr.prefix_length));
    }
    let mut nm_setting = nm_conn.ipv4.as_ref().cloned().unwrap_or_default();
    nm_setting.method = Some(method);
    nm_setting.addresses = addresses;
    if iface_ip.is_auto() {
        nm_setting.dhcp_timeout = Some(i32::MAX);
        nm_setting.route_metric = iface_ip.auto_route_metric.map(|i| i.into());
        nm_setting.dhcp_client_id = Some(nmstate_dhcp_client_id_to_nm(
            iface_ip
                .dhcp_client_id
                .as_ref()
                .unwrap_or(&Dhcpv4ClientId::LinkLayerAddress),
        ));

        apply_dhcp_opts(
            &mut nm_setting,
            iface_ip.auto_dns,
            iface_ip.auto_gateway,
            iface_ip.auto_routes,
            iface_ip.auto_table_id,
        );
        // Clean old routes
        nm_setting.gateway = None;
        nm_setting.routes = Vec::new();
        if Some(false) == iface_ip.dhcp_send_hostname {
            nm_setting.dhcp_send_hostname = Some(false);
        } else {
            nm_setting.dhcp_send_hostname = Some(true);
            if let Some(v) = iface_ip.dhcp_custom_hostname.as_deref() {
                if v.is_empty() {
                    nm_setting.dhcp_fqdn = None;
                    nm_setting.dhcp_hostname = None;
                } else {
                    // We are not verifying full spec of FQDN, just check
                    // whether it has do it not.
                    if v.contains('.') {
                        nm_setting.dhcp_fqdn = Some(v.to_string());
                        nm_setting.dhcp_hostname = None;
                    } else {
                        nm_setting.dhcp_hostname = Some(v.to_string());
                        nm_setting.dhcp_fqdn = None;
                    }
                }
            }
        }
    }
    if iface_ip.enabled {
        if let Some(routes) = routes {
            nm_setting.routes = gen_nm_ip_routes(routes, false)?;
            nm_setting.gateway = None;
        }
    } else {
        // Clean up static routes if ip is disabled
        nm_setting.routes = Vec::new();
        nm_setting.gateway = None;
    }
    if let Some(rules) = iface_ip.rules.as_ref() {
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
    let nmstate_ip_addrs: Vec<InterfaceIpAddr> = iface_ip
        .addresses
        .as_deref()
        .unwrap_or_default()
        .iter()
        .filter(|i| !i.is_auto())
        .cloned()
        .collect();
    let mut addresses: Vec<String> = Vec::new();
    let method = if iface_ip.enabled {
        match (
            iface_ip.dhcp.unwrap_or_default(),
            iface_ip.autoconf.unwrap_or_default(),
        ) {
            (true, true) => NmSettingIpMethod::Auto,
            (true, false) => NmSettingIpMethod::Dhcp,
            (false, true) => {
                return Err(NmstateError::new(
                    ErrorKind::NotImplementedError,
                    "Autoconf without DHCP is not supported yet".to_string(),
                ))
            }
            (false, false) => {
                if !nmstate_ip_addrs.is_empty() {
                    NmSettingIpMethod::Manual
                } else {
                    NmSettingIpMethod::LinkLocal
                }
            }
        }
    } else {
        NmSettingIpMethod::Disabled
    };
    for ip_addr in nmstate_ip_addrs {
        addresses.push(format!("{}/{}", ip_addr.ip, ip_addr.prefix_length));
    }
    let mut nm_setting = nm_conn.ipv6.as_ref().cloned().unwrap_or_default();
    nm_setting.method = Some(method);
    nm_setting.addresses = addresses;
    nm_setting.addr_gen_mode =
        Some(nmstate_addr_gen_mode_to_nm(iface_ip.addr_gen_mode.as_ref()));
    if iface_ip.is_auto() {
        nm_setting.dhcp_timeout = Some(i32::MAX);
        nm_setting.ra_timeout = Some(i32::MAX);
        nm_setting.dhcp_duid = Some(
            iface_ip
                .dhcp_duid
                .as_ref()
                .unwrap_or(&Dhcpv6Duid::LinkLayerAddress)
                .to_string(),
        );
        nm_setting.dhcp_iaid = Some("mac".to_string());
        if let Some(token) = iface_ip.token.as_ref() {
            if token.is_empty() || token == "::" {
                nm_setting.token = None;
            } else {
                nm_setting.token = Some(token.to_string());
            }
        }
        nm_setting.route_metric = iface_ip.auto_route_metric.map(|i| i.into());
        apply_dhcp_opts(
            &mut nm_setting,
            iface_ip.auto_dns,
            iface_ip.auto_gateway,
            iface_ip.auto_routes,
            iface_ip.auto_table_id,
        );
        // Clean old routes
        nm_setting.gateway = None;
        nm_setting.routes = Vec::new();
        if Some(false) == iface_ip.dhcp_send_hostname {
            nm_setting.dhcp_send_hostname = Some(false);
        } else {
            nm_setting.dhcp_send_hostname = Some(true);
            if let Some(v) = iface_ip.dhcp_custom_hostname.as_deref() {
                if v.is_empty() {
                    nm_setting.dhcp_hostname = None;
                } else {
                    nm_setting.dhcp_hostname = Some(v.to_string());
                }
            }
        }
    } else {
        nm_setting.token = None;
    }
    if iface_ip.enabled {
        if let Some(routes) = routes {
            nm_setting.routes = gen_nm_ip_routes(routes, true)?;
            nm_setting.gateway = None;
        }
    } else {
        // Clean up static routes if ip is disabled
        nm_setting.routes = Vec::new();
        nm_setting.gateway = None;
    }
    if let Some(rules) = iface_ip.rules.as_ref() {
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
    nm_conn: &mut NmConnection,
) -> Result<(), NmstateError> {
    let base_iface = iface.base_iface();
    if base_iface.can_have_ip() {
        gen_nm_ipv4_setting(base_iface.ipv4.as_ref(), routes, nm_conn)?;
        gen_nm_ipv6_setting(base_iface.ipv6.as_ref(), routes, nm_conn)?;
        apply_nmstate_wait_ip(base_iface, nm_conn);
    } else {
        nm_conn.ipv4 = None;
        nm_conn.ipv6 = None;
    }
    Ok(())
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

fn nmstate_dhcp_client_id_to_nm(client_id: &Dhcpv4ClientId) -> String {
    match client_id {
        Dhcpv4ClientId::LinkLayerAddress => "mac".into(),
        Dhcpv4ClientId::IaidPlusDuid => "duid".into(),
        Dhcpv4ClientId::Other(s) => s.into(),
    }
}

fn nmstate_addr_gen_mode_to_nm(addr_gen_mode: Option<&Ipv6AddrGenMode>) -> i32 {
    match addr_gen_mode {
        Some(Ipv6AddrGenMode::StablePrivacy) => ADDR_GEN_MODE_STABLE_PRIVACY,
        Some(Ipv6AddrGenMode::Eui64) | None => ADDR_GEN_MODE_EUI64,
        Some(Ipv6AddrGenMode::Other(s)) => {
            s.parse::<i32>().unwrap_or(ADDR_GEN_MODE_EUI64)
        }
    }
}

fn apply_nmstate_wait_ip(
    base_iface: &BaseInterface,
    nm_conn: &mut NmConnection,
) {
    match base_iface.wait_ip {
        Some(WaitIp::Any) => {
            if let Some(nm_ip_set) = nm_conn.ipv4.as_mut() {
                nm_ip_set.may_fail = Some(true);
            }
            if let Some(nm_ip_set) = nm_conn.ipv6.as_mut() {
                nm_ip_set.may_fail = Some(true);
            }
        }
        Some(WaitIp::Ipv4) => {
            if let Some(nm_ip_set) = nm_conn.ipv4.as_mut() {
                nm_ip_set.may_fail = Some(false);
            }
            if let Some(nm_ip_set) = nm_conn.ipv6.as_mut() {
                nm_ip_set.may_fail = Some(true);
            }
        }
        Some(WaitIp::Ipv6) => {
            if let Some(nm_ip_set) = nm_conn.ipv4.as_mut() {
                nm_ip_set.may_fail = Some(true);
            }
            if let Some(nm_ip_set) = nm_conn.ipv6.as_mut() {
                nm_ip_set.may_fail = Some(false);
            }
        }
        Some(WaitIp::Ipv4AndIpv6) => {
            if let Some(nm_ip_set) = nm_conn.ipv4.as_mut() {
                nm_ip_set.may_fail = Some(false);
            }
            if let Some(nm_ip_set) = nm_conn.ipv6.as_mut() {
                nm_ip_set.may_fail = Some(false);
            }
        }
        None => (),
    }
}
