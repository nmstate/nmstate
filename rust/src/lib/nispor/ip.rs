// SPDX-License-Identifier: Apache-2.0

use std::{collections::HashMap, str::FromStr};

use crate::{
    AddressFlag, AddressProtocol, AddressScope, ErrorKind, InterfaceIpAddr,
    InterfaceIpv4, InterfaceIpv6, InterfaceState, MergedInterface,
    MergedNetworkState, NmstateError, nispor::mptcp::get_mptcp_flags,
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
                    protocol: np_addr.protocol.map(AddressProtocol::from),
                    scope: Some(AddressScope::from(np_addr.scope)),
                    flags: if np_addr.flags.is_empty() {
                        None
                    } else {
                        Some(
                            np_addr
                                .flags
                                .iter()
                                .map(|f| AddressFlag::from(*f))
                                .collect(),
                        )
                    },
                    label: np_addr.label.clone(),
                    peer: np_addr.peer.clone(),
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
                    protocol: np_addr.protocol.map(AddressProtocol::from),
                    scope: Some(AddressScope::from(np_addr.scope)),
                    flags: if np_addr.flags.is_empty() {
                        None
                    } else {
                        Some(
                            np_addr
                                .flags
                                .iter()
                                .map(|f| AddressFlag::from(*f))
                                .collect(),
                        )
                    },
                    // IFA_LABEL is IPv4-only; IPv6 does not use it.
                    label: None,
                    peer: np_addr.peer.map(|p| p.to_string()),
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
    if let Some(nms_cur_iface) = nms_merged_iface.current.as_ref()
        && let (Some(nms_cur_ipv4), Some(nms_des_ipv4)) = (
            &nms_cur_iface.base_iface().ipv4,
            &nms_merged_iface.merged.base_iface().ipv4,
        )
    {
        // Compare without query-only fields, else kernel-assigned
        // attributes alone mark an address for removal
        let des_ips: Vec<InterfaceIpAddr> = nms_des_ipv4
            .addresses
            .as_deref()
            .unwrap_or_default()
            .iter()
            .cloned()
            .map(strip_query_only_fields)
            .collect();

        for nms_addr in nms_cur_ipv4.addresses.as_deref().unwrap_or_default() {
            // Address managed by external tool, sanitize removed it from
            // desired state, but it should stay in kernel
            if nms_addr.is_protocol_other() {
                continue;
            }
            let cmp_addr = strip_query_only_fields(nms_addr.clone());
            if !des_ips.contains(&cmp_addr) {
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
    if let Some(nms_cur_iface) = nms_merged_iface.current.as_ref()
        && let (Some(nms_cur_ipv6), Some(nms_des_ipv6)) = (
            &nms_cur_iface.base_iface().ipv6,
            &nms_merged_iface.merged.base_iface().ipv6,
        )
    {
        // Compare without query-only fields, else kernel-assigned
        // attributes alone mark an address for removal
        let des_ips: Vec<InterfaceIpAddr> = nms_des_ipv6
            .addresses
            .as_deref()
            .unwrap_or_default()
            .iter()
            .cloned()
            .map(strip_query_only_fields)
            .collect();

        for nms_addr in nms_cur_ipv6.addresses.as_deref().unwrap_or_default() {
            // Address managed by external tool, sanitize removed it from
            // desired state, but it should stay in kernel
            if nms_addr.is_protocol_other() {
                continue;
            }
            let cmp_addr = strip_query_only_fields(nms_addr.clone());
            if !des_ips.contains(&cmp_addr) {
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

/// Strip query-only kernel attributes so that address comparisons only
/// consider the user-meaningful fields (ip, prefix_length, mptcp_flags).
pub(crate) fn strip_query_only_fields(
    mut a: InterfaceIpAddr,
) -> InterfaceIpAddr {
    a.protocol = None;
    a.scope = None;
    a.flags = None;
    a.label = None;
    a.peer = None;
    a.valid_life_time = None;
    a.preferred_life_time = None;
    a
}

/// A saved IFA_PROTO address together with its interface name and all
/// kernel attributes (scope, flags, label, peer, etc.).
#[derive(Clone)]
pub(crate) struct SavedIfaProtoAddr {
    pub iface_name: String,
    pub is_ipv6: bool,
    pub conf: nispor::IpAddrConf,
}

/// Collect IFA_PROTO addresses (those with `AddressProtocol::Other`) from
/// every interface that will be touched during apply.  This includes
/// interfaces explicitly changed AND interfaces that only have route
/// changes (which NM still reapplies, potentially removing addresses).
pub(crate) fn collect_ifa_proto_addrs(
    merged_state: &MergedNetworkState,
) -> Vec<SavedIfaProtoAddr> {
    let mut result = Vec::new();
    let route_ifaces = &merged_state.routes.route_changed_ifaces;
    for merged_iface in merged_state.interfaces.iter().filter(|i| {
        i.is_changed() || route_ifaces.contains(&i.merged.name().to_string())
    }) {
        let iface_name = merged_iface.merged.name();
        let iface_state = merged_iface.merged.base_iface().state;
        if matches!(iface_state, InterfaceState::Down | InterfaceState::Absent)
        {
            continue;
        }
        let cur_iface = match merged_iface.current.as_ref() {
            Some(i) => i,
            None => continue,
        };
        let ipv4_disabled = merged_iface
            .merged
            .base_iface()
            .ipv4
            .as_ref()
            .is_some_and(|ip| !ip.enabled);
        let ipv6_disabled = merged_iface
            .merged
            .base_iface()
            .ipv6
            .as_ref()
            .is_some_and(|ip| !ip.enabled);

        if !ipv4_disabled && let Some(ipv4) = &cur_iface.base_iface().ipv4 {
            for addr in ipv4.addresses.as_deref().unwrap_or_default() {
                if addr.is_protocol_other() {
                    result.push(SavedIfaProtoAddr {
                        iface_name: iface_name.to_string(),
                        is_ipv6: false,
                        conf: nmstate_addr_to_conf(addr),
                    });
                }
            }
        }
        if !ipv6_disabled && let Some(ipv6) = &cur_iface.base_iface().ipv6 {
            for addr in ipv6.addresses.as_deref().unwrap_or_default() {
                if addr.is_protocol_other() {
                    result.push(SavedIfaProtoAddr {
                        iface_name: iface_name.to_string(),
                        is_ipv6: true,
                        conf: nmstate_addr_to_conf(addr),
                    });
                }
            }
        }
    }
    result
}

pub(crate) fn nmstate_addr_to_conf(
    addr: &InterfaceIpAddr,
) -> nispor::IpAddrConf {
    let mut conf = nispor::IpAddrConf::default();
    conf.address = addr.ip.to_string();
    conf.prefix_len = addr.prefix_length;
    if let Some(vlt) = &addr.valid_life_time {
        conf.valid_lft = vlt.clone();
    }
    if let Some(plt) = &addr.preferred_life_time {
        conf.preferred_lft = plt.clone();
    }
    if let Some(proto) = addr.protocol {
        conf.protocol = Some(nispor::AddressProtocol::from(proto));
    }
    if let Some(scope) = addr.scope {
        conf.scope = Some(nispor::AddressScope::from(scope));
    }
    if let Some(flags) = &addr.flags {
        conf.flags =
            flags.iter().map(|f| nispor::IpAddrFlag::from(*f)).collect();
    }
    conf.label = addr.label.clone();
    conf.peer = addr.peer.clone();
    conf
}

/// Re-add previously saved IFA_PROTO addresses to the kernel via nispor.
///
/// The `IfaceConf` objects carry only IP address fields (no MTU, MAC,
/// state, etc.), so nispor's `apply_iface_conf` skips the RTM_SETLINK
/// messages and only sends RTM_NEWADDR — avoiding triggering
/// NetworkManager to re-activate the connection profile.
pub(crate) async fn restore_ifa_proto_addrs(
    addrs: &[SavedIfaProtoAddr],
) -> Result<(), NmstateError> {
    if addrs.is_empty() {
        return Ok(());
    }

    // Group addresses by interface, splitting IPv4 / IPv6.
    let mut iface_map: HashMap<&str, (nispor::IpConf, nispor::IpConf)> =
        HashMap::new();
    for saved in addrs {
        let (v4, v6) = iface_map
            .entry(saved.iface_name.as_str())
            .or_insert_with(|| {
                (nispor::IpConf::default(), nispor::IpConf::default())
            });
        if saved.is_ipv6 {
            v6.addresses.push(saved.conf.clone());
        } else {
            v4.addresses.push(saved.conf.clone());
        }
    }

    let mut np_ifaces = Vec::new();
    for (iface_name, (ipv4, ipv6)) in &iface_map {
        let mut np_iface = nispor::IfaceConf::default();
        np_iface.name = iface_name.to_string();
        if !ipv4.addresses.is_empty() {
            np_iface.ipv4 = Some(ipv4.clone());
        }
        if !ipv6.addresses.is_empty() {
            np_iface.ipv6 = Some(ipv6.clone());
        }
        np_ifaces.push(np_iface);
    }

    let mut net_conf = nispor::NetConf::default();
    net_conf.ifaces = Some(np_ifaces);

    log::info!(
        "Restoring {} IFA_PROTO address(es) on {} interface(s)",
        addrs.len(),
        iface_map.len(),
    );
    if let Err(e) = net_conf.apply_async().await {
        return Err(NmstateError::new(
            ErrorKind::PluginFailure,
            format!(
                "Failed to restore IFA_PROTO addresses: {}, {}",
                e.kind, e.msg
            ),
        ));
    }
    Ok(())
}
