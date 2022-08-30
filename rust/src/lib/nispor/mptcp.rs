// SPDX-License-Identifier: Apache-2.0

use std::convert::TryFrom;

use crate::{
    ip::{is_ipv6_unicast_link_local, is_ipv6_unicast_local},
    BaseInterface, MptcpAddressFlag, MptcpConfig,
};

pub(crate) fn get_mptcp_flags(
    np_iface: &nispor::Iface,
    ip_addr: &str,
) -> Vec<MptcpAddressFlag> {
    let mut flags = Vec::new();
    if let Some(mptcp_addrs) = np_iface.mptcp.as_ref() {
        for mptcp_addr in mptcp_addrs {
            if mptcp_addr.address.to_string().as_str() == ip_addr {
                if let Some(np_flags) = mptcp_addr.flags.as_ref() {
                    for np_flag in np_flags {
                        match MptcpAddressFlag::try_from(*np_flag) {
                            Ok(f) => flags.push(f),
                            Err(e) => {
                                log::warn!("{}", e);
                                continue;
                            }
                        }
                    }
                }
            }
        }
    }
    flags
}

pub(crate) fn get_iface_mptcp_conf(
    iface: &BaseInterface,
) -> Option<MptcpConfig> {
    let mut flags: Vec<MptcpAddressFlag> = Vec::new();
    let mut has_mptcp_valid_ip_addr = false;

    if let Some(addrs) = iface.ipv4.as_ref().and_then(|i| i.addresses.as_ref())
    {
        for addr in addrs {
            if let std::net::IpAddr::V4(ip_addr) = &addr.ip {
                if ip_addr.is_loopback()
                    || ip_addr.is_link_local()
                    || ip_addr.is_multicast()
                {
                    continue;
                }
            }
            has_mptcp_valid_ip_addr = true;
            if let Some(mptcp_flags) = addr.mptcp_flags.as_ref() {
                if flags.is_empty() {
                    flags = mptcp_flags.clone();
                } else if &flags != mptcp_flags {
                    return None;
                }
            }
        }
    }
    if let Some(addrs) = iface.ipv6.as_ref().and_then(|i| i.addresses.as_ref())
    {
        for addr in addrs {
            if let std::net::IpAddr::V6(ip_addr) = &addr.ip {
                // TODO: Skip IPv6 privacy extensions address also.
                if ip_addr.is_loopback()
                    || ip_addr.is_multicast()
                    || is_ipv6_unicast_local(ip_addr)
                    || is_ipv6_unicast_link_local(ip_addr)
                {
                    continue;
                }
            }
            has_mptcp_valid_ip_addr = true;
            if let Some(mptcp_flags) = addr.mptcp_flags.as_ref() {
                if flags.is_empty() {
                    flags = mptcp_flags.clone();
                } else if &flags != mptcp_flags {
                    return None;
                }
            }
        }
    }

    if has_mptcp_valid_ip_addr {
        Some(MptcpConfig {
            address_flags: Some(flags),
        })
    } else {
        None
    }
}
