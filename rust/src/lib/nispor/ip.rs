// SPDX-License-Identifier: Apache-2.0

use std::str::FromStr;

use crate::{
    nispor::mptcp::get_mptcp_flags, InterfaceIpAddr, InterfaceIpv4,
    InterfaceIpv6, MergedInterface,
};

pub(crate) fn np_ipv4_to_nmstate(
    np_iface: &nispor::Iface,
    running_config_only: bool,
) -> Option<InterfaceIpv4> {
    if let Some(np_ip) = &np_iface.ipv4 {
        let mut ip = InterfaceIpv4 {
            enabled: !np_ip.addresses.is_empty(),
            enabled_defined: true,
            ..Default::default()
        };
        ip.forwarding = np_iface.ipv4.as_ref().and_then(|v| v.forwarding);
        if !ip.enabled {
            return Some(ip);
        }
        let mut addresses = Vec::new();
        for np_addr in &np_ip.addresses {
            if np_addr.valid_lft != "forever" {
                ip.dhcp = Some(true);
                if running_config_only {
                    continue;
                }
            }
            match std::net::IpAddr::from_str(np_addr.address.as_str()) {
                Ok(i) => addresses.push(InterfaceIpAddr {
                    ip: i,
                    prefix_length: np_addr.prefix_len,
                    mptcp_flags: {
                        let mptcp_flags =
                            get_mptcp_flags(np_iface, np_addr.address.as_str());

                        if !mptcp_flags.is_empty() {
                            Some(mptcp_flags)
                        } else {
                            None
                        }
                    },
                    valid_life_time: if np_addr.valid_lft != "forever" {
                        Some(np_addr.valid_lft.clone())
                    } else {
                        None
                    },
                    preferred_life_time: if np_addr.preferred_lft != "forever" {
                        Some(np_addr.preferred_lft.clone())
                    } else {
                        None
                    },
                    ..Default::default()
                }),
                Err(e) => {
                    log::warn!(
                        "BUG: nispor got invalid IP address {}, error {}",
                        np_addr.address.as_str(),
                        e
                    );
                }
            }
        }
        ip.addresses = Some(addresses);

        Some(ip)
    } else {
        // IP might just disabled
        Some(InterfaceIpv4 {
            enabled: false,
            enabled_defined: true,
            ..Default::default()
        })
    }
}

pub(crate) fn np_ipv6_to_nmstate(
    np_iface: &nispor::Iface,
    running_config_only: bool,
) -> Option<InterfaceIpv6> {
    if let Some(np_ip) = &np_iface.ipv6 {
        let mut ip = InterfaceIpv6 {
            enabled: !np_ip.addresses.is_empty(),
            enabled_defined: true,
            ..Default::default()
        };

        if !ip.enabled {
            return Some(ip);
        }
        if let Some(token) = np_ip.token.as_ref() {
            ip.token = Some(token.to_string());
        }

        let mut addresses = Vec::new();
        for np_addr in &np_ip.addresses {
            if np_addr.valid_lft != "forever" {
                ip.autoconf = Some(true);
                if running_config_only {
                    continue;
                }
            }
            match std::net::IpAddr::from_str(np_addr.address.as_str()) {
                Ok(i) => addresses.push(InterfaceIpAddr {
                    ip: i,
                    prefix_length: np_addr.prefix_len,
                    mptcp_flags: {
                        let mptcp_flags =
                            get_mptcp_flags(np_iface, np_addr.address.as_str());

                        if !mptcp_flags.is_empty() {
                            Some(mptcp_flags)
                        } else {
                            None
                        }
                    },
                    valid_life_time: if np_addr.valid_lft != "forever" {
                        Some(np_addr.valid_lft.clone())
                    } else {
                        None
                    },
                    preferred_life_time: if np_addr.preferred_lft != "forever" {
                        Some(np_addr.preferred_lft.clone())
                    } else {
                        None
                    },
                    ..Default::default()
                }),
                Err(e) => {
                    log::warn!(
                        "BUG: nispor got invalid IP address {}, error {}",
                        np_addr.address.as_str(),
                        e
                    );
                }
            }
        }
        ip.addresses = Some(addresses);
        Some(ip)
    } else {
        // IP might just disabled
        Some(InterfaceIpv6 {
            enabled: false,
            enabled_defined: true,
            ..Default::default()
        })
    }
}

pub(crate) fn nmstate_ipv4_to_np(
    nms_merged_iface: &MergedInterface,
) -> nispor::IpConf {
    let mut np_ip_conf = nispor::IpConf::default();

    // delete ip addresses not in desired state
    if let Some(nms_cur_iface) = nms_merged_iface.current.as_ref() {
        if let (Some(nms_cur_ipv4), Some(nms_des_ipv4)) = (
            &nms_cur_iface.base_iface().ipv4,
            &nms_merged_iface.merged.base_iface().ipv4,
        ) {
            let des_ips: Vec<_> = nms_des_ipv4
                .addresses
                .as_deref()
                .unwrap_or_default()
                .iter()
                .collect();

            for nms_addr in
                nms_cur_ipv4.addresses.as_deref().unwrap_or_default()
            {
                if !des_ips.contains(&nms_addr) {
                    np_ip_conf.addresses.push({
                        let mut ip_conf = nispor::IpAddrConf::default();
                        ip_conf.address = nms_addr.ip.to_string();
                        ip_conf.prefix_len = nms_addr.prefix_length;
                        ip_conf.remove = true;
                        ip_conf
                    });
                }
            }
        }
    }

    // Add new ip address entries before deleting
    if let Some(nms_des_ipv4) = &nms_merged_iface.merged.base_iface().ipv4 {
        for nms_addr in nms_des_ipv4.addresses.as_deref().unwrap_or_default() {
            np_ip_conf.addresses.push({
                let mut ip_conf = nispor::IpAddrConf::default();
                ip_conf.address = nms_addr.ip.to_string();
                ip_conf.prefix_len = nms_addr.prefix_length;
                ip_conf
            });
        }
    }
    np_ip_conf
}

pub(crate) fn nmstate_ipv6_to_np(
    nms_merged_iface: &MergedInterface,
) -> nispor::IpConf {
    let mut np_ip_conf = nispor::IpConf::default();

    // delete ip addresses not in desired state
    if let Some(nms_cur_iface) = nms_merged_iface.current.as_ref() {
        if let (Some(nms_cur_ipv6), Some(nms_des_ipv6)) = (
            &nms_cur_iface.base_iface().ipv6,
            &nms_merged_iface.merged.base_iface().ipv6,
        ) {
            let des_ips: Vec<_> = nms_des_ipv6
                .addresses
                .as_deref()
                .unwrap_or_default()
                .iter()
                .collect();

            for nms_addr in
                nms_cur_ipv6.addresses.as_deref().unwrap_or_default()
            {
                if !des_ips.contains(&nms_addr) {
                    np_ip_conf.addresses.push({
                        let mut ip_conf = nispor::IpAddrConf::default();
                        ip_conf.address = nms_addr.ip.to_string();
                        ip_conf.prefix_len = nms_addr.prefix_length;
                        ip_conf.remove = true;
                        ip_conf
                    });
                }
            }
        }
    }

    // Add new ip address entries after deleting
    if let Some(nms_des_ipv6) = &nms_merged_iface.merged.base_iface().ipv6 {
        for nms_addr in nms_des_ipv6.addresses.as_deref().unwrap_or_default() {
            np_ip_conf.addresses.push({
                let mut ip_conf = nispor::IpAddrConf::default();
                ip_conf.address = nms_addr.ip.to_string();
                ip_conf.prefix_len = nms_addr.prefix_length;
                ip_conf
            });
        }
    }
    np_ip_conf
}
