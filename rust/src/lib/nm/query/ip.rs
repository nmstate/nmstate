// SPDX-License-Identifier: Apache-2.0

use std::ops::BitXor;

use super::super::nm_dbus::{NmSettingIp, NmSettingIpMethod};

use super::dns::nm_dns_to_nmstate;

use crate::{
    Dhcpv4ClientId, Dhcpv6Duid, InterfaceIpv4, InterfaceIpv6, Ipv6AddrGenMode,
    WaitIp,
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
                "dhcp_client_id",
                "dns",
                "auto_dns",
                "auto_routes",
                "auto_gateway",
                "auto_table_id",
            ],
            dns: Some(nm_dns_to_nmstate(nm_ip_setting)),
            dhcp_client_id: nm_dhcp_client_id_to_nmstate(nm_ip_setting),
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
                "dhcp_duid",
                "addr_gen_mode",
            ],
            dns: Some(nm_dns_to_nmstate(nm_ip_setting)),
            dhcp_duid: nm_dhcp_duid_to_nmstate(nm_ip_setting),
            addr_gen_mode: {
                if enabled {
                    nm_ipv6_addr_gen_mode_to_nmstate(nm_ip_setting)
                } else {
                    None
                }
            },
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
