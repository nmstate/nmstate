// SPDX-License-Identifier: Apache-2.0

use std::ops::BitXor;

use super::super::nm_dbus::{
    NmIpRouteRuleAction, NmSettingIp, NmSettingIpMethod,
};

use super::dns::nm_dns_to_nmstate;

use crate::{
    AddressFamily, Dhcpv4ClientId, Dhcpv6Duid, InterfaceIpv4, InterfaceIpv6,
    Ipv6AddrGenMode, RouteRuleAction, RouteRuleEntry, WaitIp,
};

const ADDR_GEN_MODE_EUI64: i32 = 0;
const ADDR_GEN_MODE_STABLE_PRIVACY: i32 = 1;
const ADDR_GEN_MODE_STABLE_DEFAULT_OR_EUI64: i32 = 2;
const ADDR_GEN_MODE_STABLE_DEFAULT: i32 = 3;

pub(crate) fn nm_ip_setting_to_nmstate4(
    nm_ip_setting: &NmSettingIp,
) -> InterfaceIpv4 {
    if let Some(nm_ip_method) = &nm_ip_setting.method {
        let (enabled, dhcp) = match nm_ip_method {
            NmSettingIpMethod::Disabled => (false, Some(false)),
            NmSettingIpMethod::LinkLocal
            | NmSettingIpMethod::Manual
            | NmSettingIpMethod::Shared => (true, Some(false)),
            NmSettingIpMethod::Auto => (true, Some(true)),
            _ => {
                log::warn!("Unexpected NM IP method {:?}", nm_ip_method);
                (true, None)
            }
        };
        let dhcp_send_hostname = if enabled && dhcp == Some(true) {
            nm_ip_setting.dhcp_send_hostname.unwrap_or(true)
        } else {
            false
        };

        let (auto_dns, auto_gateway, auto_routes, auto_table_id) =
            parse_dhcp_opts(nm_ip_setting);
        InterfaceIpv4 {
            enabled,
            enabled_defined: true,
            dhcp,
            auto_dns,
            auto_routes,
            auto_gateway,
            auto_table_id,
            dns: Some(nm_dns_to_nmstate("", nm_ip_setting)),
            rules: nm_rules_to_nmstate(false, nm_ip_setting),
            dhcp_client_id: if enabled && dhcp == Some(true) {
                nm_dhcp_client_id_to_nmstate(nm_ip_setting)
            } else {
                None
            },
            auto_route_metric: nm_ip_setting.route_metric.map(|i| i as u32),
            dhcp_send_hostname: if enabled && dhcp == Some(true) {
                Some(dhcp_send_hostname)
            } else {
                None
            },
            dhcp_custom_hostname: if enabled
                && dhcp == Some(true)
                && dhcp_send_hostname
            {
                nm_ip_setting
                    .dhcp_fqdn
                    .as_ref()
                    .or(nm_ip_setting.dhcp_hostname.as_ref())
                    .cloned()
            } else {
                None
            },
            ..Default::default()
        }
    } else {
        InterfaceIpv4::default()
    }
}

pub(crate) fn nm_ip_setting_to_nmstate6(
    iface_name: &str,
    nm_ip_setting: &NmSettingIp,
) -> InterfaceIpv6 {
    if let Some(nm_ip_method) = &nm_ip_setting.method {
        let (enabled, dhcp, autoconf) = match nm_ip_method {
            NmSettingIpMethod::Disabled => (false, Some(false), Some(false)),
            NmSettingIpMethod::LinkLocal
            | NmSettingIpMethod::Manual
            | NmSettingIpMethod::Shared => (true, Some(false), Some(false)),
            NmSettingIpMethod::Auto => (true, Some(true), Some(true)),
            NmSettingIpMethod::Dhcp => (true, Some(true), Some(false)),
            NmSettingIpMethod::Ignore => (true, Some(false), Some(false)),
        };
        let (auto_dns, auto_gateway, auto_routes, auto_table_id) =
            parse_dhcp_opts(nm_ip_setting);
        let mut ret = InterfaceIpv6 {
            enabled,
            enabled_defined: true,
            dhcp,
            autoconf,
            auto_dns,
            auto_routes,
            auto_gateway,
            auto_table_id,
            dns: Some(nm_dns_to_nmstate(iface_name, nm_ip_setting)),
            rules: nm_rules_to_nmstate(true, nm_ip_setting),
            dhcp_duid: nm_dhcp_duid_to_nmstate(nm_ip_setting),
            addr_gen_mode: {
                if enabled {
                    nm_ipv6_addr_gen_mode_to_nmstate(nm_ip_setting)
                } else {
                    None
                }
            },
            auto_route_metric: nm_ip_setting.route_metric.map(|i| i as u32),
            dhcp_send_hostname: if enabled && dhcp == Some(true) {
                Some(nm_ip_setting.dhcp_send_hostname.unwrap_or(true))
            } else {
                None
            },
            dhcp_custom_hostname: if enabled && dhcp == Some(true) {
                nm_ip_setting.dhcp_hostname.clone()
            } else {
                None
            },
            ..Default::default()
        };
        // NetworkManager only set IPv6 token to kernel when IPv6 autoconf
        // done. But nmstate should not wait DHCP, hence instead of depending
        // on nispor kernel IPv6 token, we set IPv6 token based on information
        // provided by NM connection.
        if let Some(token) = nm_ip_setting.token.as_ref() {
            ret.token = Some(token.to_string());
        }
        ret
    } else {
        InterfaceIpv6::default()
    }
}

// return (auto_dns, auto_gateway, auto_routes, auto_table_id)
fn parse_dhcp_opts(
    nm_setting: &NmSettingIp,
) -> (Option<bool>, Option<bool>, Option<bool>, Option<u32>) {
    if nm_setting.method == Some(NmSettingIpMethod::Auto)
        || nm_setting.method == Some(NmSettingIpMethod::Dhcp)
    {
        (
            Some(nm_setting.ignore_auto_dns.map(flip_bool).unwrap_or(true)),
            Some(nm_setting.never_default.map(flip_bool).unwrap_or(true)),
            Some(nm_setting.ignore_auto_routes.map(flip_bool).unwrap_or(true)),
            Some(nm_setting.route_table.unwrap_or_default()),
        )
    } else {
        (None, None, None, None)
    }
}

fn flip_bool(v: bool) -> bool {
    v.bitxor(true)
}

fn nm_dhcp_duid_to_nmstate(nm_setting: &NmSettingIp) -> Option<Dhcpv6Duid> {
    match nm_setting.dhcp_duid.as_deref() {
        Some("ll") => Some(Dhcpv6Duid::LinkLayerAddress),
        Some("llt") => Some(Dhcpv6Duid::LinkLayerAddressPlusTime),
        Some("uuid") => Some(Dhcpv6Duid::Uuid),
        Some(nm_duid) => Some(Dhcpv6Duid::Other(nm_duid.to_string())),
        None => None,
    }
}

fn nm_dhcp_client_id_to_nmstate(
    nm_setting: &NmSettingIp,
) -> Option<Dhcpv4ClientId> {
    match nm_setting.dhcp_client_id.as_deref() {
        Some("mac") => Some(Dhcpv4ClientId::LinkLayerAddress),
        Some("duid") => Some(Dhcpv4ClientId::IaidPlusDuid),
        Some(nm_id) => Some(Dhcpv4ClientId::Other(nm_id.to_string())),
        None => None,
    }
}

fn nm_ipv6_addr_gen_mode_to_nmstate(
    nm_setting: &NmSettingIp,
) -> Option<Ipv6AddrGenMode> {
    match nm_setting.addr_gen_mode.as_ref() {
        Some(&ADDR_GEN_MODE_EUI64) => Some(Ipv6AddrGenMode::Eui64),
        Some(&ADDR_GEN_MODE_STABLE_PRIVACY) => {
            Some(Ipv6AddrGenMode::StablePrivacy)
        }
        Some(&ADDR_GEN_MODE_STABLE_DEFAULT_OR_EUI64) => {
            Some(Ipv6AddrGenMode::Eui64)
        }
        Some(&ADDR_GEN_MODE_STABLE_DEFAULT) => {
            Some(Ipv6AddrGenMode::StablePrivacy)
        }
        Some(s) => Some(Ipv6AddrGenMode::Other(format!("{s}"))),
        // According to NM document, the None in dbus means stable privacy.
        None => Some(Ipv6AddrGenMode::StablePrivacy),
    }
}

pub(crate) fn query_nmstate_wait_ip(
    ipv4_set: Option<&NmSettingIp>,
    ipv6_set: Option<&NmSettingIp>,
) -> Option<WaitIp> {
    match (ipv4_set, ipv6_set) {
        (Some(ipv4_set), Some(ipv6_set)) => {
            match (ipv4_set.may_fail.as_ref(), ipv6_set.may_fail.as_ref()) {
                (Some(true), Some(true))
                | (Some(true), None)
                | (None, Some(true))
                | (None, None) => Some(WaitIp::Any),
                (Some(true), Some(false)) | (None, Some(false)) => {
                    Some(WaitIp::Ipv6)
                }
                (Some(false), Some(true)) | (Some(false), None) => {
                    Some(WaitIp::Ipv4)
                }
                (Some(false), Some(false)) => Some(WaitIp::Ipv4AndIpv6),
            }
        }
        (Some(ipv4_set), None) => match ipv4_set.may_fail.as_ref() {
            Some(true) | None => Some(WaitIp::Any),
            Some(false) => Some(WaitIp::Ipv4),
        },
        (None, Some(ipv6_set)) => match ipv6_set.may_fail.as_ref() {
            Some(true) | None => Some(WaitIp::Any),
            Some(false) => Some(WaitIp::Ipv6),
        },
        (None, None) => None,
    }
}

fn nm_rules_to_nmstate(
    is_ipv6: bool,
    ip_set: &NmSettingIp,
) -> Option<Vec<RouteRuleEntry>> {
    let mut ret = Vec::new();
    for nm_rule in ip_set.route_rules.as_slice() {
        let mut rule = RouteRuleEntry::new();
        if is_ipv6 {
            rule.family = Some(AddressFamily::IPv6);
        } else {
            rule.family = Some(AddressFamily::IPv4);
        }
        if let Some(v) = nm_rule.priority.as_ref() {
            rule.priority = Some(*v as i64);
        }
        if let (Some(from), Some(from_len)) =
            (nm_rule.from.as_ref(), nm_rule.from_len.as_ref())
        {
            rule.ip_from = Some(format!("{from}/{from_len}"));
        }
        if let (Some(to), Some(to_len)) =
            (nm_rule.to.as_ref(), nm_rule.to_len.as_ref())
        {
            rule.ip_to = Some(format!("{to}/{to_len}"));
        }
        if let Some(v) = nm_rule.table.as_ref() {
            rule.table_id = Some(*v);
        }
        if let Some(v) = nm_rule.fw_mark.as_ref() {
            rule.fwmark = Some(*v);
        }
        if let Some(v) = nm_rule.fw_mask.as_ref() {
            rule.fwmask = Some(*v);
        }
        if let Some(v) = nm_rule.iifname.as_ref() {
            rule.iif = Some(v.to_string());
        }
        if let Some(v) = nm_rule.suppress_prefixlength {
            match u32::try_from(v) {
                Ok(i) => rule.suppress_prefix_length = Some(i),
                Err(e) => {
                    log::warn!(
                        "BUG: Failed to convert `suppress_prefixlength` \
                        got from NM: {v} to u32: {e}"
                    );
                }
            }
        }
        if let Some(v) = nm_rule.action.as_ref() {
            rule.action = Some(match v {
                NmIpRouteRuleAction::Blackhole => RouteRuleAction::Blackhole,
                NmIpRouteRuleAction::Unreachable => {
                    RouteRuleAction::Unreachable
                }
                NmIpRouteRuleAction::Prohibit => RouteRuleAction::Prohibit,
                _ => {
                    log::warn!("Unknown NM IP route rule action {:?}", v);
                    continue;
                }
            });
        }
        ret.push(rule);
    }
    Some(ret)
}
