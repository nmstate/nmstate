// SPDX-License-Identifier: Apache-2.0

use std::str::FromStr;

use super::super::{
    dns::{
        extract_ipv6_link_local_iface_from_dns_srv, get_cur_dns_ifaces,
        store_dns_config_to_desired_iface, store_dns_config_to_iface,
        store_dns_search_or_option_to_iface,
    },
    error::nm_error_to_nmstate,
    nm_dbus::{
        NmActiveConnection, NmApi, NmDevice, NmDnsEntry, NmGlobalDnsConfig,
        NmSettingIp,
    },
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

pub(crate) async fn retrieve_dns_state(
    nm_api: &mut NmApi<'_>,
    ifaces: &Interfaces,
) -> Result<DnsState, NmstateError> {
    let config_dns_info = retrieve_configured_dns_info(nm_api, ifaces).await?;
    let running_dns_servers = retrieve_running_dns_servers(nm_api).await?;
    let running_dns_info = DnsClientState {
        server: Some(running_dns_servers),
        search: config_dns_info.search.clone(),
        options: config_dns_info.options.clone(),
        ..Default::default()
    };

    Ok(DnsState {
        running: Some(running_dns_info),
        config: Some(config_dns_info),
    })
}

async fn retrieve_running_dns_servers(
    nm_api: &mut NmApi<'_>,
) -> Result<Vec<String>, NmstateError> {
    let mut servers: Vec<String> = Vec::new();
    let mut has_split_dns = false;

    let mut nm_dns_entries = nm_api
        .get_dns_configuration()
        .await
        .map_err(nm_error_to_nmstate)?;
    nm_dns_entries.sort_unstable_by_key(|d| d.priority);

    // If there are global nameservers, only those are used
    for nm_dns_entry in nm_dns_entries
        .iter()
        .filter(|entry| entry.interface.is_empty())
    {
        if !nm_dns_entry.domains.is_empty() {
            has_split_dns = true;
        }
        servers.extend(nm_dns_srvs_to_nmstate(nm_dns_entry));
    }

    if has_split_dns {
        log::warn!(
            "Running DNS config has split-DNS, but nmstate doesn't support \
             it. Its info may be inaccurate."
        );
    }

    if !servers.is_empty() {
        return Ok(servers);
    }

    // If there are no global nameservers, those from connections are used
    for nm_dns_entry in nm_dns_entries {
        servers.extend(nm_dns_srvs_to_nmstate(&nm_dns_entry));
        if nm_dns_entry.priority < 0 {
            // Per NM's doc, ignore remaining entries if priority<0
            break;
        }
    }

    Ok(servers)
}

async fn retrieve_configured_dns_info(
    nm_api: &mut NmApi<'_>,
    ifaces: &Interfaces,
) -> Result<DnsClientState, NmstateError> {
    let mut use_global_servers = false;
    let mut use_global_searches_and_options = false;
    let mut servers: Vec<String> = Vec::new();
    let mut searches: Vec<String> = Vec::new();
    let mut options: Vec<String> = Vec::new();

    // First fill from global config
    let nm_global_dns_conf = nm_api
        .get_global_dns_configuration()
        .await
        .map_err(nm_error_to_nmstate)?;

    if let Some(nm_global_dns_conf) = nm_global_dns_conf {
        use_global_searches_and_options = true;
        searches.extend_from_slice(&nm_global_dns_conf.searches);
        options.extend_from_slice(&nm_global_dns_conf.options);

        if let Some(nm_domain_conf) = nm_global_dns_conf.domains.get("*") {
            use_global_servers = true;
            servers.extend_from_slice(&nm_domain_conf.servers)
        }

        if nm_global_dns_conf.domains.len() > 1 {
            log::warn!("Ignoring split-DNS nameservers (not supported)");
        }
    }

    // Fill servers from ifaces only if they are not defined in global config.
    // Fill searches and options from ifaces only if neither them nor servers
    // are defined in global config.
    if !use_global_servers {
        let mut nm_ifaces_dns_confs: Vec<&DnsClientState> = Vec::new();
        for iface in ifaces.kernel_ifaces.values() {
            if let Some(ip_conf) = iface.base_iface().ipv6.as_ref() {
                if let Some(dns_conf) = ip_conf.dns.as_ref() {
                    nm_ifaces_dns_confs.push(dns_conf);
                }
            }
            if let Some(ip_conf) = iface.base_iface().ipv4.as_ref() {
                if let Some(dns_conf) = ip_conf.dns.as_ref() {
                    nm_ifaces_dns_confs.push(dns_conf);
                }
            }
        }
        nm_ifaces_dns_confs
            .sort_unstable_by_key(|d| d.priority.unwrap_or_default());

        for dns_conf in nm_ifaces_dns_confs {
            if let Some(srvs) = dns_conf.server.as_ref() {
                servers.extend_from_slice(srvs);
            }

            if !use_global_searches_and_options {
                if let Some(schs) = dns_conf.search.as_ref() {
                    for sch in schs {
                        if sch.starts_with("~") {
                            // Ignore routing only domains
                            continue;
                        }
                        if !searches.contains(sch) {
                            searches.push(sch.clone())
                        }
                    }
                }
                if let Some(opts) = dns_conf.options.as_ref() {
                    for opt in opts {
                        if !options.contains(opt) {
                            options.push(opt.clone());
                        }
                    }
                }
            }

            if dns_conf.priority.unwrap_or(0) < 0 {
                // Per NM's doc, ignore remaining entries if priority<0
                break;
            }
        }
    }

    let servers_or_searches_set = !servers.is_empty() || !searches.is_empty();
    Ok(DnsClientState {
        server: servers_or_searches_set.then_some(servers),
        search: servers_or_searches_set.then_some(searches),
        options: (!options.is_empty()).then_some(options),
        ..Default::default()
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

pub(crate) async fn store_dns_config(
    merged_state: &mut MergedNetworkState,
    nm_api: &mut NmApi<'_>,
    nm_acs: &[NmActiveConnection],
    nm_devs: &[NmDevice],
) -> Result<(), NmstateError> {
    if merged_state.dns.is_changed()
        || merged_state.dns.is_desired()
        || !cur_dns_ifaces_still_valid_for_dns(&merged_state.interfaces)
    {
        purge_global_dns_config(nm_api).await?;

        if merged_state.dns.is_search_or_option_only() {
            log::info!(
                "Using interface level DNS for special use case: only static \
                 DNS search and/or DNS option desired"
            );
            // we cannot use global DNS in this case because global DNS suppress
            // DNS nameserver learn from DHCP/autoconf.
            store_dns_search_or_option_to_iface(merged_state, nm_acs, nm_devs)?;
        } else if is_iface_dns_desired(merged_state) {
            if let Err(e) =
                store_dns_config_to_iface(merged_state, nm_acs, nm_devs)
            {
                log::info!(
                    "Cannot store DNS to interface profile: {e}, will try to \
                     set via global DNS"
                );
                store_dns_config_via_global_api(
                    nm_api,
                    merged_state.dns.servers.as_slice(),
                    merged_state.dns.searches.as_slice(),
                    merged_state.dns.options.as_slice(),
                )
                .await?;
            }
        } else if merged_state.dns.is_purge() {
            // Also need to purge interface level DNS
            store_dns_config_to_iface(merged_state, nm_acs, nm_devs).ok();
        } else {
            store_dns_config_via_global_api(
                nm_api,
                merged_state.dns.servers.as_slice(),
                merged_state.dns.searches.as_slice(),
                merged_state.dns.options.as_slice(),
            )
            .await?;
            // Still store DNS into desired interface to provides backwards
            // compatibility for user who uses NM keyfiles only:
            // https://github.com/coreos/fedora-coreos-tracker/issues/1947
            store_dns_config_to_desired_iface(merged_state);
        }
    }
    Ok(())
}

async fn store_dns_config_via_global_api(
    nm_api: &mut NmApi<'_>,
    servers: &[String],
    searches: &[String],
    options: &[String],
) -> Result<(), NmstateError> {
    log::info!(
        "Storing DNS to NetworkManager via global dns API, this will cause \
         __all__ interface level DNS settings been ignored"
    );

    let nm_config = NmGlobalDnsConfig::new_wildcard(
        searches.to_vec(),
        servers.to_vec(),
        options.to_vec(),
    );
    log::debug!("Applying NM global DNS config {nm_config:?}");
    nm_api
        .set_global_dns_configuration(&nm_config)
        .await
        .map_err(nm_error_to_nmstate)?;
    Ok(())
}

async fn purge_global_dns_config(
    nm_api: &mut NmApi<'_>,
) -> Result<(), NmstateError> {
    let cur_dns = nm_api
        .get_global_dns_configuration()
        .await
        .map_err(nm_error_to_nmstate)?;
    if cur_dns.is_none() || cur_dns.is_some_and(|cur_dns| !cur_dns.is_empty()) {
        log::debug!("Purging NM Global DNS config");
        nm_api
            .set_global_dns_configuration(&NmGlobalDnsConfig::default())
            .await
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}

// To save us from NM iface-DNS mess, we prefer global DNS over iface DNS,
// unless use case like:
//  1. Has IPv6 link-local address as name server: e.g. `fe80::deef:1%eth1`
//  2. User want static DNS server appended before dynamic one. In this case,
//     user should define `auto-dns: true` explicitly along with static DNS.
//  3. User want to force DNS server stored in interface for static IP
//     interface. This case, user need to state static DNS config along with
//     static IP config.
fn is_iface_dns_desired(merged_state: &MergedNetworkState) -> bool {
    if extract_ipv6_link_local_iface_from_dns_srv(
        merged_state.dns.servers.as_slice(),
    )
    .is_some()
    {
        log::info!(
            "Using interface level DNS for special use case: IPv6 link-local \
             address as DNS nameserver"
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
                "Using interface level DNS for special use case: appending \
                 static DNS nameserver before dynamic ones."
            );
            return true;
        }
        if iface.base_iface().ipv4.as_ref().map(|i| i.is_static()) == Some(true)
            || iface.base_iface().ipv6.as_ref().map(|i| i.is_static())
                == Some(true)
        {
            log::info!(
                "Using interface level DNS for special use case: explicitly \
                 requested interface level DNS via defining static IP and \
                 static DNS nameserver."
            );
            return true;
        }
    }
    false
}

fn cur_dns_ifaces_still_valid_for_dns(
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
