// SPDX-License-Identifier: Apache-2.0

use nmstate::{
    DispatchGlobalConfig, DnsState, HostNameState, NetworkState,
    OvnConfiguration, OvsDbGlobalConfig, RouteRules, Routes,
};
use serde::Serialize;
use serde_yaml::Value;

use crate::error::CliError;

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub(crate) struct SortedNetworkState {
    #[serde(skip_serializing_if = "Option::is_none")]
    hostname: Option<HostNameState>,
    #[serde(rename = "dns-resolver", skip_serializing_if = "Option::is_none")]
    dns: Option<DnsState>,
    #[serde(rename = "route-rules", default)]
    rules: RouteRules,
    routes: Routes,
    #[serde(skip_serializing_if = "DispatchGlobalConfig::is_none")]
    dispatch: DispatchGlobalConfig,
    interfaces: Vec<Value>,
    #[serde(rename = "ovs-db", skip_serializing_if = "Option::is_none")]
    ovsdb: Option<OvsDbGlobalConfig>,
    #[serde(skip_serializing_if = "OvnConfiguration::is_none")]
    ovn: OvnConfiguration,
}

const IFACE_TOP_PRIORTIES: [&str; 2] = ["name", "type"];

// Ordering the outputs
pub(crate) fn show(matches: &clap::ArgMatches) -> Result<String, CliError> {
    let mut net_state = NetworkState::new();
    if matches.is_present("KERNEL") {
        net_state.set_kernel_only(true);
    }
    if matches.is_present("RUNNING_CONFIG_ONLY") {
        net_state.set_running_config_only(true);
    }
    net_state.set_include_secrets(matches.is_present("SHOW_SECRETS"));
    net_state.retrieve()?;
    Ok(if let Some(ifname) = matches.value_of("IFNAME") {
        let mut new_net_state = filter_net_state_with_iface(&net_state, ifname);
        new_net_state.set_kernel_only(matches.is_present("KERNEL"));
        if matches.is_present("JSON") {
            serde_json::to_string_pretty(&new_net_state)?
        } else {
            serde_yaml::to_string(&new_net_state)?
        }
    } else if matches.is_present("JSON") {
        serde_json::to_string_pretty(&sort_netstate(net_state)?)?
    } else {
        serde_yaml::to_string(&sort_netstate(net_state)?)?
    })
}

pub(crate) fn sort_netstate(
    net_state: NetworkState,
) -> Result<SortedNetworkState, CliError> {
    let mut ifaces = net_state.interfaces.to_vec();
    ifaces.sort_by(|a, b| a.name().cmp(b.name()));

    if let Value::Sequence(ifaces) = serde_yaml::to_value(&ifaces)? {
        let mut new_ifaces = Vec::new();
        for iface_v in ifaces {
            if let Value::Mapping(iface) = iface_v {
                let mut new_iface = serde_yaml::Mapping::new();
                for top_property in &IFACE_TOP_PRIORTIES {
                    if let Some(v) =
                        iface.get(&Value::String(top_property.to_string()))
                    {
                        new_iface.insert(
                            Value::String(top_property.to_string()),
                            v.clone(),
                        );
                    }
                }
                for (k, v) in iface.iter() {
                    if let Value::String(ref name) = k {
                        if IFACE_TOP_PRIORTIES.contains(&name.as_str()) {
                            continue;
                        }
                    }
                    new_iface.insert(k.clone(), v.clone());
                }

                new_ifaces.push(Value::Mapping(new_iface));
            }
        }
        return Ok(SortedNetworkState {
            hostname: net_state.hostname,
            interfaces: new_ifaces,
            routes: net_state.routes,
            rules: net_state.rules,
            dns: net_state.dns,
            ovsdb: net_state.ovsdb,
            ovn: net_state.ovn,
            dispatch: net_state.dispatch,
        });
    }

    Ok(SortedNetworkState {
        hostname: net_state.hostname,
        interfaces: Vec::new(),
        routes: net_state.routes,
        rules: net_state.rules,
        dns: net_state.dns,
        ovsdb: net_state.ovsdb,
        ovn: net_state.ovn,
        dispatch: net_state.dispatch,
    })
}

fn filter_net_state_with_iface(
    net_state: &NetworkState,
    iface_name: &str,
) -> NetworkState {
    let mut ret = NetworkState::new();
    for iface in net_state.interfaces.to_vec() {
        if iface.name() == iface_name {
            ret.append_interface_data(iface.clone())
        }
    }
    if let Some(running_rts) = net_state.routes.running.as_ref() {
        for rt in running_rts {
            if rt.next_hop_iface.as_ref() == Some(&iface_name.to_string()) {
                if let Some(rts) = ret.routes.running.as_mut() {
                    rts.push(rt.clone());
                } else {
                    ret.routes.running = Some(vec![rt.clone()]);
                }
            }
        }
    }
    let mut route_table_ids = Vec::new();

    if let Some(config_rts) = net_state.routes.config.as_ref() {
        for rt in config_rts {
            if rt.next_hop_iface.as_ref() == Some(&iface_name.to_string()) {
                if let Some(table_id) = rt.table_id {
                    route_table_ids.push(table_id);
                }
                if let Some(rts) = ret.routes.config.as_mut() {
                    rts.push(rt.clone());
                } else {
                    ret.routes.config = Some(vec![rt.clone()]);
                }
            }
        }
    }

    if let Some(config_rules) = net_state.rules.config.as_ref() {
        for rule in config_rules {
            if let Some(table_id) = rule.table_id {
                if route_table_ids.contains(&table_id) {
                    if let Some(rules) = ret.rules.config.as_mut() {
                        rules.push(rule.clone());
                    } else {
                        ret.rules.config = Some(vec![rule.clone()]);
                    }
                }
            }
        }
    }

    ret
}
