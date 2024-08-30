// SPDX-License-Identifier: Apache-2.0

use std::str::FromStr;

use super::super::{
    dns::{extract_ipv6_link_local_iface_from_dns_srv, get_cur_dns_ifaces},
    error::nm_error_to_nmstate,
    nm_dbus::{NmApi, NmDnsEntry, NmGlobalDnsConfig, NmSettingIp},
};

use crate::{
    ip::is_ipv6_unicast_link_local, DnsClientState, DnsState, Interfaces,
    MergedInterfaces, MergedNetworkState, NmstateError,
};

pub(crate) fn nm_dns_to_nmstate(
    iface_name: &str,
    nm_ip_setting: &NmSettingIp,
) -> DnsClientState {
    let mut servers = Vec::new();
    if let Some(srvs) = nm_ip_setting.dns.as_ref() {
        for srv in srvs {
            if let Ok(ip) = std::net::Ipv6Addr::from_str(srv.as_str()) {
                if is_ipv6_unicast_link_local(&ip) {
                    servers.push(format!("{srv}%{iface_name}"));
                } else {
                    servers.push(srv.to_string());
                }
            } else {
                servers.push(srv.to_string());
            }
        }
    }

    DnsClientState {
        server: if nm_ip_setting.dns.is_none() {
            None
        } else {
            Some(servers)
        },
        search: nm_ip_setting.dns_search.clone(),
        options: nm_ip_setting.dns_options.clone(),
        priority: nm_ip_setting.dns_priority,
    }
}

pub(crate) fn retrieve_dns_info(
    nm_api: &mut NmApi,
    ifaces: &Interfaces,
) -> Result<DnsState, NmstateError> {
    let mut nm_dns_entires = nm_api
        .get_dns_configuration()
        .map_err(nm_error_to_nmstate)?;
    nm_dns_entires.sort_unstable_by_key(|d| d.priority);
    let mut running_srvs: Vec<String> = Vec::new();
    let mut running_schs: Vec<String> = Vec::new();
    for nm_dns_entry in nm_dns_entires {
        running_srvs.extend(nm_dns_srvs_to_nmstate(&nm_dns_entry));
        running_schs.extend_from_slice(nm_dns_entry.domains.as_slice());
    }

    let mut dns_confs: Vec<&DnsClientState> = Vec::new();
    for iface in ifaces.kernel_ifaces.values() {
        if let Some(ip_conf) = iface.base_iface().ipv6.as_ref() {
            if let Some(dns_conf) = ip_conf.dns.as_ref() {
                dns_confs.push(dns_conf);
            }
        }
        if let Some(ip_conf) = iface.base_iface().ipv4.as_ref() {
            if let Some(dns_conf) = ip_conf.dns.as_ref() {
                dns_confs.push(dns_conf);
            }
        }
    }
    dns_confs.sort_unstable_by_key(|d| d.priority.unwrap_or_default());
    let mut config_srvs: Vec<String> = Vec::new();
    let mut config_schs: Vec<String> = Vec::new();
    for dns_conf in dns_confs {
        if let Some(srvs) = dns_conf.server.as_ref() {
            config_srvs.extend_from_slice(srvs);
        }
        if let Some(schs) = dns_conf.search.as_ref() {
            config_schs.extend_from_slice(schs);
        }
    }

    // The DNS options is not provided via `NmApi.get_dns_configuration()`,
    // The data stored in active connections will not be refreshed after
    // reapply.
    // The data stored in applied connection will not do validation.
    let mut dns_options: Vec<String> = Vec::new();

    let nm_conns = nm_api
        .applied_connections_get()
        .map_err(nm_error_to_nmstate)?;
    for nm_conn in &nm_conns {
        if let Some(opts) =
            nm_conn.ipv4.as_ref().and_then(|i| i.dns_options.as_deref())
        {
            for opt in opts {
                if !dns_options.contains(opt) {
                    dns_options.push(opt.clone());
                }
            }
        }
        if let Some(opts) =
            nm_conn.ipv6.as_ref().and_then(|i| i.dns_options.as_deref())
        {
            for opt in opts {
                if !dns_options.contains(opt) {
                    dns_options.push(opt.clone());
                }
            }
        }
    }
    // The order of DNS options does not matters, hence no need to sort the
    // DNS option using DNS priority.
    dns_options.sort_unstable();

    Ok(DnsState {
        running: Some(DnsClientState {
            server: Some(running_srvs),
            search: Some(running_schs),
            options: if dns_options.is_empty() {
                None
            } else {
                Some(dns_options.clone())
            },
            ..Default::default()
        }),
        config: Some(DnsClientState {
            server: if config_srvs.is_empty() && config_schs.is_empty() {
                None
            } else {
                Some(config_srvs.clone())
            },
            search: if config_srvs.is_empty() && config_schs.is_empty() {
                None
            } else {
                Some(config_schs)
            },
            options: if dns_options.is_empty() {
                None
            } else {
                Some(dns_options)
            },
            ..Default::default()
        }),
    })
}

fn nm_dns_srvs_to_nmstate(nm_dns_entry: &NmDnsEntry) -> Vec<String> {
    let mut srvs = Vec::new();
    for srv in nm_dns_entry.name_servers.as_slice() {
        if let Ok(ip) = std::net::Ipv6Addr::from_str(srv.as_str()) {
            if is_ipv6_unicast_link_local(&ip)
                && !nm_dns_entry.interface.is_empty()
            {
                srvs.push(format!("{}%{}", srv, nm_dns_entry.interface));
                continue;
            } else {
                srvs.push(srv.to_string());
            }
        } else {
            srvs.push(srv.to_string());
        }
    }
    srvs
}

pub(crate) fn store_dns_config_via_global_api(
    nm_api: &mut NmApi,
    servers: &[String],
    searches: &[String],
    options: &[String],
) -> Result<(), NmstateError> {
    log::info!(
        "Storing DNS to NetworkManager via global dns API, \
        this will cause __all__ interface level DNS settings been ignored"
    );

    let nm_config = NmGlobalDnsConfig::new_wildcard(
        searches.to_vec(),
        servers.to_vec(),
        options.to_vec(),
    );
    log::debug!("Applying NM global DNS config {:?}", nm_config);
    nm_api
        .set_global_dns_configuration(&nm_config)
        .map_err(nm_error_to_nmstate)?;
    Ok(())
}

pub(crate) fn purge_global_dns_config(
    nm_api: &mut NmApi,
) -> Result<(), NmstateError> {
    let cur_dns = nm_api
        .get_global_dns_configuration()
        .map_err(nm_error_to_nmstate)?;
    if !cur_dns.is_empty() {
        log::debug!("Purging NM Global DNS config");
        nm_api
            .set_global_dns_configuration(&NmGlobalDnsConfig::default())
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}

pub(crate) fn nm_global_dns_to_nmstate(
    nm_global_dns_conf: &NmGlobalDnsConfig,
) -> DnsState {
    let mut config = DnsClientState::new();

    config.options = if nm_global_dns_conf.options.is_empty() {
        None
    } else {
        Some(nm_global_dns_conf.options.clone())
    };
    config.search = Some(nm_global_dns_conf.searches.clone());
    config.server =
        if let Some(nm_domain_conf) = nm_global_dns_conf.domains.get("*") {
            Some(nm_domain_conf.servers.clone())
        } else {
            Some(Vec::new())
        };

    DnsState {
        running: Some(config.clone()),
        config: Some(config),
    }
}

// To save us from NM iface-DNS mess, we prefer global DNS over iface DNS,
// unless use case like:
//  1. Has IPv6 link-local address as name server: e.g. `fe80::deef:1%eth1`
//  2. User want static DNS server appended before dynamic one. In this case,
//     user should define `auto-dns: true` explicitly along with static DNS.
//  3. User want to force DNS server stored in interface for static IP
//     interface. This case, user need to state static DNS config along with
//     static IP config.
pub(crate) fn is_iface_dns_desired(merged_state: &MergedNetworkState) -> bool {
    if extract_ipv6_link_local_iface_from_dns_srv(
        merged_state.dns.servers.as_slice(),
    )
    .is_some()
    {
        log::info!(
            "Using interface level DNS for special use case: \
            IPv6 link-local address as DNS nameserver"
        );
        return true;
    }

    for iface in merged_state
        .interfaces
        .kernel_ifaces
        .values()
        .filter_map(|i| i.for_apply.as_ref())
    {
        if iface
            .base_iface()
            .ipv4
            .as_ref()
            .map(|i| i.is_auto() && i.auto_dns == Some(true))
            == Some(true)
            || iface
                .base_iface()
                .ipv6
                .as_ref()
                .map(|i| i.is_auto() && i.auto_dns == Some(true))
                == Some(true)
        {
            log::info!(
                "Using interface level DNS for special use case: \
                appending static DNS nameserver before dynamic ones."
            );
            return true;
        }
        if iface.base_iface().ipv4.as_ref().map(|i| i.is_static()) == Some(true)
            || iface.base_iface().ipv6.as_ref().map(|i| i.is_static())
                == Some(true)
        {
            log::info!(
                "Using interface level DNS for special use case: \
                explicitly requested interface level DNS via \
                defining static IP and static DNS nameserver."
            );
            return true;
        }
    }
    false
}

pub(crate) fn cur_dns_ifaces_still_valid_for_dns(
    merged_ifaces: &MergedInterfaces,
) -> bool {
    let (cur_v4_ifaces, cur_v6_ifaces) = get_cur_dns_ifaces(merged_ifaces);
    for iface_name in &cur_v4_ifaces {
        if let Some(iface) = merged_ifaces.kernel_ifaces.get(iface_name) {
            if iface.is_changed() && !iface.is_iface_valid_for_dns(false) {
                return false;
            }
        }
    }
    for iface_name in &cur_v6_ifaces {
        if let Some(iface) = merged_ifaces.kernel_ifaces.get(iface_name) {
            if iface.is_changed() && !iface.is_iface_valid_for_dns(true) {
                return false;
            }
        }
    }
    true
}
