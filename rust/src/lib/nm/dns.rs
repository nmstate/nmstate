// SPDX-License-Identifier: Apache-2.0

use crate::{dns::parse_dns_ipv6_link_local_srv, ip::is_ipv6_addr};
use crate::{
    DnsClientState, ErrorKind, Interface, InterfaceType, MergedInterfaces,
    MergedNetworkState, NmstateError,
};

const DEFAULT_DNS_PRIORITY: i32 = 40;

pub(crate) fn store_dns_config(
    merged_state: &mut MergedNetworkState,
) -> Result<(), NmstateError> {
    if merged_state.dns.is_changed() {
        let (cur_v4_ifaces, cur_v6_ifaces) =
            get_cur_dns_ifaces(&merged_state.interfaces);
        let (v4_iface_name, v6_iface_name) = reselect_dns_ifaces(
            merged_state,
            cur_v4_ifaces.as_slice(),
            cur_v6_ifaces.as_slice(),
        );

        purge_dns_config(false, cur_v4_ifaces.as_slice(), merged_state);
        purge_dns_config(true, cur_v6_ifaces.as_slice(), merged_state);
        save_dns_to_iface(&v4_iface_name, &v6_iface_name, merged_state)?;
    }
    Ok(())
}

// If DNS changed or desired, we find out interface to hold the DNS entry in the
// order of:
//  * If current interface which holding the DNS still valid for DNS also listed
//    in desire state
//  * Interfaces in desired with manual IP stack enabled or `auto_dns: false`
//  * Interfaces in current with manual IP stack enabled or `auto_dns: false`
//  * TODO: loopback interface
pub(crate) fn reselect_dns_ifaces(
    merged_state: &MergedNetworkState,
    cur_v4_ifaces: &[String],
    cur_v6_ifaces: &[String],
) -> (String, String) {
    let ipv4_iface =
        find_dns_iface(false, &merged_state.interfaces, cur_v4_ifaces)
            .unwrap_or_default();

    let ipv6_iface = extract_ipv6_link_local_iface_from_dns_srv(
        merged_state.dns.servers.as_slice(),
    )
    .or_else(|| find_dns_iface(true, &merged_state.interfaces, cur_v6_ifaces))
    .unwrap_or_default();

    (ipv4_iface, ipv6_iface)
}

// Find interface with DHCP disabled and IP enabled from desired interfaces.
fn find_dns_iface(
    is_ipv6: bool,
    merged_ifaces: &MergedInterfaces,
    cur_dns_ifaces: &[String],
) -> Option<String> {
    // Try using current DNS interface if in desired list
    for iface_name in cur_dns_ifaces {
        if let Some(iface) = merged_ifaces.kernel_ifaces.get(iface_name) {
            if iface.is_changed() && iface.is_iface_valid_for_dns(is_ipv6) {
                return Some(iface_name.to_string());
            }
        }
    }

    // Do not use loopback interface for DNS
    for (iface_name, iface) in
        merged_ifaces.kernel_ifaces.iter().filter(|(_, i)| {
            i.merged.iface_type() != InterfaceType::Loopback && i.is_changed()
        })
    {
        if iface.is_iface_valid_for_dns(is_ipv6) {
            return Some(iface_name.to_string());
        }
    }

    // Try again among undesired current interface
    for (iface_name, iface) in merged_ifaces
        .kernel_ifaces
        .iter()
        .filter(|(_, i)| i.merged.iface_type() != InterfaceType::Loopback)
    {
        if iface.is_iface_valid_for_dns(is_ipv6) {
            return Some(iface_name.to_string());
        }
    }

    None
}

fn extract_ipv6_link_local_iface_from_dns_srv(
    srvs: &[String],
) -> Option<String> {
    for srv in srvs {
        let splits: Vec<&str> = srv.split('%').collect();
        if splits.len() == 2 && !splits[1].is_empty() {
            return Some(splits[1].to_string());
        }
    }
    None
}

pub(crate) fn purge_dns_config(
    is_ipv6: bool,
    ifaces: &[String],
    merged_state: &mut MergedNetworkState,
) {
    for iface_name in ifaces {
        if let Some(iface) =
            merged_state.interfaces.kernel_ifaces.get_mut(iface_name)
        {
            if !iface.is_changed() {
                iface.mark_as_changed();
                if let Some(apply_iface) = iface.for_apply.as_mut() {
                    apply_iface.base_iface_mut().ipv4 =
                        iface.merged.base_iface_mut().ipv4.clone();
                    apply_iface.base_iface_mut().ipv6 =
                        iface.merged.base_iface_mut().ipv6.clone();
                }
            }
            if let Some(apply_iface) = iface.for_apply.as_mut() {
                set_iface_dns_conf(
                    is_ipv6,
                    apply_iface,
                    Vec::new(),
                    Vec::new(),
                    None,
                );
            }
        }
    }
}

fn save_dns_to_iface(
    v4_iface_name: &str,
    v6_iface_name: &str,
    merged_state: &mut MergedNetworkState,
) -> Result<(), NmstateError> {
    let mut v4_servers = Vec::new();
    let mut v6_servers = Vec::new();
    let prefer_ipv6_srv = merged_state
        .dns
        .servers
        .get(0)
        .map(|s| is_ipv6_addr(s.as_str()))
        .unwrap_or_default();
    for srv in merged_state.dns.servers.as_slice() {
        if is_ipv6_addr(srv) {
            v6_servers.push(srv.to_string())
        } else {
            v4_servers.push(srv.to_string())
        }
    }
    if !v6_servers.is_empty() {
        _save_dns_to_iface(
            true,
            v6_iface_name,
            v6_servers,
            merged_state,
            prefer_ipv6_srv,
        )?;
    }
    if !v4_servers.is_empty() {
        _save_dns_to_iface(
            false,
            v4_iface_name,
            v4_servers,
            merged_state,
            !prefer_ipv6_srv,
        )?;
    }
    Ok(())
}

// Argument `preferred`: true will save the searches
// Assuming all IPv6 link local address is pointing to specified argument
// `iface_name` iface.
fn _save_dns_to_iface(
    is_ipv6: bool,
    iface_name: &str,
    mut servers: Vec<String>,
    merged_state: &mut MergedNetworkState,
    preferred: bool,
) -> Result<(), NmstateError> {
    for srv in servers.as_mut_slice() {
        if let Some((ip, _)) = parse_dns_ipv6_link_local_srv(srv)? {
            srv.replace_range(.., ip.to_string().as_str());
        }
    }

    if iface_name.is_empty() {
        let e = NmstateError::new(
            ErrorKind::InvalidArgument,
            format!(
                "Failed to find suitable(IP enabled with DHCP off \
                or auto-dns: false) interface for DNS server {servers:?}"
            ),
        );
        log::error!("{}", e);
        return Err(e);
    }

    if let Some(iface) =
        merged_state.interfaces.kernel_ifaces.get_mut(iface_name)
    {
        if !iface.is_changed() {
            iface.mark_as_changed();
            if let Some(apply_iface) = iface.for_apply.as_mut() {
                apply_iface.base_iface_mut().ipv4 =
                    iface.merged.base_iface_mut().ipv4.clone();
                apply_iface.base_iface_mut().ipv6 =
                    iface.merged.base_iface_mut().ipv6.clone();
            }
        }
        if let Some(apply_iface) = iface.for_apply.as_mut() {
            if preferred {
                set_iface_dns_conf(
                    is_ipv6,
                    apply_iface,
                    servers,
                    merged_state.dns.searches.clone(),
                    Some(DEFAULT_DNS_PRIORITY),
                );
            } else {
                set_iface_dns_conf(
                    is_ipv6,
                    apply_iface,
                    servers,
                    Vec::new(),
                    Some(DEFAULT_DNS_PRIORITY + 10),
                );
            }
        }
    } else {
        return Err(NmstateError::new(
            ErrorKind::Bug,
            format!(
                "_save_dns_to_iface(): Failed to find interface \
                {iface_name} among {merged_state:?}"
            ),
        ));
    }

    Ok(())
}

fn set_iface_dns_conf(
    is_ipv6: bool,
    iface: &mut Interface,
    servers: Vec<String>,
    searches: Vec<String>,
    priority: Option<i32>,
) {
    let dns_conf = DnsClientState {
        server: Some(servers),
        search: Some(searches),
        priority,
    };
    if is_ipv6 {
        if let Some(ip_conf) = iface.base_iface_mut().ipv6.as_mut() {
            ip_conf.dns = Some(dns_conf);
        } else {
            // Should never happen
            log::error!("BUG: The dns interface is hold None IP {:?}", iface);
        }
    } else if let Some(ip_conf) = iface.base_iface_mut().ipv4.as_mut() {
        ip_conf.dns = Some(dns_conf);
    } else {
        // Should never happen
        log::error!("BUG: The dns interface is hold None IP {:?}", iface);
    }
}

fn get_cur_dns_ifaces(
    merged_ifaces: &MergedInterfaces,
) -> (Vec<String>, Vec<String>) {
    let mut v4_ifaces: Vec<String> = Vec::new();
    let mut v6_ifaces: Vec<String> = Vec::new();
    for iface in merged_ifaces
        .kernel_ifaces
        .values()
        .filter(|i| i.current.is_some())
    {
        let cur_iface = if let Some(c) = iface.current.as_ref() {
            c
        } else {
            continue;
        };

        if let Some(ipv4) = &cur_iface.base_iface().ipv4 {
            if ipv4.enabled {
                if let Some(dns_conf) = &ipv4.dns {
                    if !dns_conf.is_null()
                        && !v4_ifaces.contains(&cur_iface.name().to_string())
                    {
                        v4_ifaces.push(cur_iface.name().to_string())
                    }
                }
            }
        }
        if let Some(ipv6) = &cur_iface.base_iface().ipv6 {
            if ipv6.enabled {
                if let Some(dns_conf) = &ipv6.dns {
                    if !dns_conf.is_null()
                        && !v6_ifaces.contains(&cur_iface.name().to_string())
                    {
                        v6_ifaces.push(cur_iface.name().to_string())
                    }
                }
            }
        }
    }
    (v4_ifaces, v6_ifaces)
}
