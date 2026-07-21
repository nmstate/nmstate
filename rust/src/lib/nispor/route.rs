// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use log::warn;

use crate::{
    ErrorKind, Interface, Interfaces, MergedRoutes, NmstateError, RouteEntry,
    RouteType, Routes,
};

const SUPPORTED_ROUTE_SCOPE: [nispor::RouteScope; 2] =
    [nispor::RouteScope::Universe, nispor::RouteScope::Link];

const SUPPORTED_ROUTE_PROTOCOL: [nispor::RouteProtocol; 7] = [
    nispor::RouteProtocol::Boot,
    nispor::RouteProtocol::Static,
    nispor::RouteProtocol::Ra,
    nispor::RouteProtocol::Dhcp,
    nispor::RouteProtocol::Mrouted,
    nispor::RouteProtocol::KeepAlived,
    nispor::RouteProtocol::Babel,
];

const SUPPORTED_STATIC_ROUTE_PROTOCOL: [nispor::RouteProtocol; 2] =
    [nispor::RouteProtocol::Boot, nispor::RouteProtocol::Static];

const IPV4_DEFAULT_GATEWAY: &str = "0.0.0.0/0";
const IPV6_DEFAULT_GATEWAY: &str = "::/0";
const IPV4_EMPTY_NEXT_HOP_ADDRESS: &str = "0.0.0.0";
const IPV6_EMPTY_NEXT_HOP_ADDRESS: &str = "::";

// kernel values
const RTAX_MTU: u32 = 2;
const RTAX_CWND: u32 = 7;

pub(crate) async fn get_routes(
    running_config_only: bool,
    ifaces: &Interfaces,
) -> Routes {
    let mut ret = Routes::new();
    let mut np_routes: Vec<nispor::Route> = Vec::new();
    let route_type = [
        nispor::RouteType::BlackHole,
        nispor::RouteType::Unreachable,
        nispor::RouteType::Prohibit,
    ];
    let protocols = if running_config_only {
        SUPPORTED_STATIC_ROUTE_PROTOCOL.as_slice()
    } else {
        SUPPORTED_ROUTE_PROTOCOL.as_slice()
    };

    for protocol in protocols {
        let mut rt_filter = nispor::NetStateRouteFilter::default();
        rt_filter.protocol = Some(*protocol);
        let mut filter = nispor::NetStateFilter::minimum();
        filter.route = Some(rt_filter);
        match nispor::NetState::retrieve_with_filter_async(&filter).await {
            Ok(np_state) => {
                for np_rt in np_state.routes {
                    np_routes.push(np_rt);
                }
            }
            Err(e) => {
                log::warn!(
                    "Failed to retrieve {protocol:?} route via nispor: {e}"
                );
            }
        }
    }

    let table_id_to_vrf_names: HashMap<u32, &str> =
        ifaces
            .kernel_ifaces
            .values()
            .filter(|i| i.is_up())
            .filter_map(|iface| {
                if let Interface::Vrf(vrf_iface) = iface {
                    vrf_iface.vrf.as_ref().and_then(|v| v.table_id).map(
                        |table_id| (table_id, vrf_iface.base.name.as_str()),
                    )
                } else {
                    None
                }
            })
            .collect();

    if !running_config_only {
        let mut running_routes = Vec::new();
        for np_route in np_routes
            .iter()
            .filter(|np_route| SUPPORTED_ROUTE_SCOPE.contains(&np_route.scope))
        {
            if is_multipath(np_route) {
                for route in
                    flat_multipath_route(np_route, &table_id_to_vrf_names)
                {
                    running_routes.push(route);
                }
            } else if route_type.contains(&np_route.route_type) {
                running_routes.push(np_routetype_to_nmstate(
                    np_route,
                    &table_id_to_vrf_names,
                ));
            } else if np_route.oif.is_some() {
                running_routes.push(np_route_to_nmstate(
                    np_route,
                    &table_id_to_vrf_names,
                ));
            }
        }
        ret.running = Some(running_routes);
    }

    let mut config_routes = Vec::new();
    for np_route in np_routes.iter().filter(|np_route| {
        SUPPORTED_ROUTE_SCOPE.contains(&np_route.scope)
            && SUPPORTED_STATIC_ROUTE_PROTOCOL.contains(&np_route.protocol)
    }) {
        if is_multipath(np_route) {
            for route in flat_multipath_route(np_route, &table_id_to_vrf_names)
            {
                config_routes.push(route);
            }
        } else if route_type.contains(&np_route.route_type) {
            config_routes.push(np_routetype_to_nmstate(
                np_route,
                &table_id_to_vrf_names,
            ));
        } else if np_route.oif.is_some() {
            config_routes
                .push(np_route_to_nmstate(np_route, &table_id_to_vrf_names));
        }
    }
    ret.config = Some(config_routes);
    ret
}

fn np_routetype_to_nmstate(
    np_route: &nispor::Route,
    table_id_to_vrf_names: &HashMap<u32, &str>,
) -> RouteEntry {
    let destination = match &np_route.dst {
        Some(dst) => Some(dst.to_string()),
        None => match np_route.address_family {
            nispor::AddressFamily::Ipv4 => {
                Some(IPV4_DEFAULT_GATEWAY.to_string())
            }
            nispor::AddressFamily::Ipv6 => {
                Some(IPV6_DEFAULT_GATEWAY.to_string())
            }
            _ => {
                warn!(
                    "Route {:?} is holding unknown IP family {:?}",
                    np_route, np_route.address_family
                );
                None
            }
        },
    };

    let mut route_entry = RouteEntry::new();
    route_entry.destination = destination;
    if np_route.address_family == nispor::AddressFamily::Ipv6 {
        route_entry.next_hop_iface = np_route.oif.as_ref().cloned();
    }
    route_entry.metric = np_route.metric.map(i64::from);
    route_entry.table_id = Some(np_route.table);
    route_entry.vrf_name = table_id_to_vrf_names
        .get(&np_route.table)
        .map(|n| n.to_string());
    match np_route.route_type {
        nispor::RouteType::BlackHole => {
            route_entry.route_type = Some(RouteType::Blackhole)
        }
        nispor::RouteType::Unreachable => {
            route_entry.route_type = Some(RouteType::Unreachable)
        }
        nispor::RouteType::Prohibit => {
            route_entry.route_type = Some(RouteType::Prohibit)
        }
        _ => {
            log::debug!("Got unsupported route {np_route:?}");
        }
    }
    // according to `man ip-route`, cwnd is useless without the lock flag, so
    // we require both cwnd and its lock flag to consider cwnd as set.
    let lock = np_route.lock.unwrap_or(0);
    let cwnd_lock = lock & (1 << RTAX_CWND) != 0;
    route_entry.cwnd = if cwnd_lock { np_route.cwnd } else { None };
    let mtu_lock = lock & (1 << RTAX_MTU) != 0;
    route_entry.lock_mtu = mtu_lock.then_some(true);

    route_entry
}

fn np_route_to_nmstate(
    np_route: &nispor::Route,
    table_id_to_vrf_names: &HashMap<u32, &str>,
) -> RouteEntry {
    let destination = match &np_route.dst {
        Some(dst) => Some(dst.to_string()),
        None => match np_route.address_family {
            nispor::AddressFamily::Ipv4 => {
                Some(IPV4_DEFAULT_GATEWAY.to_string())
            }
            nispor::AddressFamily::Ipv6 => {
                Some(IPV6_DEFAULT_GATEWAY.to_string())
            }
            _ => {
                warn!(
                    "Route {:?} is holding unknown IP family {:?}",
                    np_route, np_route.address_family
                );
                None
            }
        },
    };

    let next_hop_addr = if let Some(via) = &np_route.via {
        Some(via.to_string())
    } else if let Some(gateway) = &np_route.gateway {
        Some(gateway.to_string())
    } else {
        match np_route.address_family {
            nispor::AddressFamily::Ipv4 => {
                Some(IPV4_EMPTY_NEXT_HOP_ADDRESS.to_string())
            }
            nispor::AddressFamily::Ipv6 => {
                Some(IPV6_EMPTY_NEXT_HOP_ADDRESS.to_string())
            }
            _ => {
                warn!(
                    "Route {:?} is holding unknown IP family {:?}",
                    np_route, np_route.address_family
                );
                None
            }
        }
    };

    let source = np_route.prefered_src.as_ref().map(|src| src.to_string());
    let mut route_entry = RouteEntry::new();
    route_entry.destination = destination;
    route_entry.next_hop_iface = np_route.oif.as_ref().cloned();
    route_entry.next_hop_addr = next_hop_addr;
    route_entry.source = source;
    route_entry.metric = np_route.metric.map(i64::from);
    route_entry.table_id = Some(np_route.table);
    route_entry.vrf_name = table_id_to_vrf_names
        .get(&np_route.table)
        .map(|n| n.to_string());
    // according to `man ip-route`, cwnd is useless without the lock flag, so
    // we require both cwnd and its lock flag to consider cwnd as set.
    let lock = np_route.lock.unwrap_or(0);
    let cwnd_lock = lock & (1 << RTAX_CWND) != 0;
    route_entry.cwnd = if cwnd_lock { np_route.cwnd } else { None };
    route_entry.initcwnd = np_route.initcwnd;
    route_entry.initrwnd = np_route.initrwnd;
    route_entry.mtu = np_route.mtu;
    let mtu_lock = lock & (1 << RTAX_MTU) != 0;
    route_entry.lock_mtu = mtu_lock.then_some(true);
    route_entry.quickack = np_route.quickack.map(|q| q > 0);
    route_entry.advmss = np_route.advmss;

    route_entry
}

fn is_multipath(np_route: &nispor::Route) -> bool {
    np_route
        .multipath
        .as_ref()
        .map(|m| !m.is_empty())
        .unwrap_or_default()
}

fn flat_multipath_route(
    np_route: &nispor::Route,
    table_id_to_vrf_names: &HashMap<u32, &str>,
) -> Vec<RouteEntry> {
    let mut ret: Vec<RouteEntry> = Vec::new();
    if let Some(mpath_routes) = np_route.multipath.as_ref() {
        for mp_route in mpath_routes {
            let mut new_np_route = np_route.clone();
            new_np_route.via = Some(mp_route.via.to_string());
            new_np_route.oif = Some(mp_route.iface.to_string());
            let mut route =
                np_route_to_nmstate(&new_np_route, table_id_to_vrf_names);
            if np_route.address_family == nispor::AddressFamily::Ipv4 {
                route.weight = Some(mp_route.weight);
            }
            ret.push(route);
        }
    }
    ret
}

fn nmstate_to_nispor_route_conf(
    nmstate_rt: &RouteEntry,
) -> Result<nispor::RouteConf, NmstateError> {
    let mut ret = nispor::RouteConf::default();

    ret.remove = nmstate_rt.is_absent();
    ret.dst = nmstate_rt.destination.clone().unwrap_or_default();
    ret.oif.clone_from(&nmstate_rt.next_hop_iface);
    ret.via.clone_from(&nmstate_rt.next_hop_addr);
    ret.metric = nmstate_rt.metric.and_then(|m| u32::try_from(m).ok());
    if let Some(table_id) = nmstate_rt.table_id {
        if table_id > u8::MAX.into() {
            return Err(NmstateError::new(
                ErrorKind::NotImplementedError,
                format!(
                    "nispor apply does not support route table ID bigger than \
                     {} yet, got {}, ignoring",
                    u8::MAX,
                    table_id
                ),
            ));
        } else {
            ret.table = Some(table_id as u8);
        }
    }
    if nmstate_rt.weight.is_some() {
        return Err(NmstateError::new(
            ErrorKind::NotImplementedError,
            "nispor apply does not support route weight yet".into(),
        ));
    }

    if nmstate_rt.route_type.is_some() {
        return Err(NmstateError::new(
            ErrorKind::NotImplementedError,
            "nispor apply does not support route type yet".into(),
        ));
    }

    if nmstate_rt.cwnd.is_some() {
        return Err(NmstateError::new(
            ErrorKind::NotImplementedError,
            "nispor apply does not support route congestion window yet".into(),
        ));
    }
    Ok(ret)
}

pub(crate) fn gen_nispor_route_confs(
    merged_routes: &MergedRoutes,
) -> Result<Vec<nispor::RouteConf>, NmstateError> {
    validate_routes(merged_routes)?;
    let mut ret = Vec::new();
    for nmstate_rt in merged_routes.changed_routes.as_slice() {
        ret.push(nmstate_to_nispor_route_conf(nmstate_rt)?)
    }
    Ok(ret)
}

fn validate_routes(merged_routes: &MergedRoutes) -> Result<(), NmstateError> {
    for iface in merged_routes.route_changed_ifaces.as_slice() {
        let iface_routes = if let Some(r) = merged_routes.merged.get(iface) {
            r
        } else {
            continue;
        };
        let mut hashed_rts: HashMap<(&str, u32, u32), &RouteEntry> =
            HashMap::new();
        for rt in iface_routes {
            if rt.weight.is_some() {
                return Err(NmstateError::new(
                    ErrorKind::NotSupportedError,
                    "Kernel mode does not support ECMP routes".to_string(),
                ));
            }

            // The `Routes::validate()` already confirmed non-absent routes
            // always has destination.
            // The `merged_routes.merged` does not have absent route.
            let dst = if let Some(dst) = rt.destination.as_deref() {
                dst
            } else {
                continue;
            };

            // Key on the metric and table the kernel will actually use, so a
            // metric-less desired route conflicts with an existing route that
            // the kernel reports with the coerced default metric (e.g. IPv6
            // default route metric 1024).
            if hashed_rts
                .insert(
                    (dst, rt.effective_table_id(), rt.effective_metric()),
                    rt,
                )
                .is_some()
            {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Multiple routes to {dst} are sharing the same metric \
                         and table, please use `state: absent` to remove \
                         others."
                    ),
                ));
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn route(
        dst: &str,
        via: &str,
        metric: Option<i64>,
        table: u32,
    ) -> RouteEntry {
        RouteEntry {
            destination: Some(dst.to_string()),
            next_hop_iface: Some("eth1".to_string()),
            next_hop_addr: Some(via.to_string()),
            metric,
            table_id: Some(table),
            ..Default::default()
        }
    }

    fn merged_for(routes: Vec<RouteEntry>) -> MergedRoutes {
        let mut merged = HashMap::new();
        merged.insert("eth1".to_string(), routes);
        MergedRoutes {
            merged,
            route_changed_ifaces: vec!["eth1".to_string()],
            ..Default::default()
        }
    }

    // Kernel reports the existing IPv6 default route with metric 1024 while the
    // desired route omits the metric. Both must be treated as conflicting.
    #[test]
    fn test_metricless_ipv6_conflicts_with_kernel_default() {
        let merged = merged_for(vec![
            route("::/0", "2001:db8:1::3", Some(1024), 200),
            route("::/0", "2001:db8:1::2", None, 200),
        ]);
        let err = validate_routes(&merged).unwrap_err();
        assert_eq!(err.kind(), ErrorKind::InvalidArgument);
    }

    // IPv4 default metric is 0, so a metric-less route and an explicit metric 0
    // route to the same destination conflict.
    #[test]
    fn test_ipv4_metricless_conflicts_with_metric_zero() {
        let merged = merged_for(vec![
            route("0.0.0.0/0", "192.0.2.1", Some(0), 200),
            route("0.0.0.0/0", "192.0.2.2", None, 200),
        ]);
        let err = validate_routes(&merged).unwrap_err();
        assert_eq!(err.kind(), ErrorKind::InvalidArgument);
    }

    // An unset table resolves to the main table, so it conflicts with an
    // explicit table 254.
    #[test]
    fn test_default_table_conflicts_with_explicit_main() {
        let merged = merged_for(vec![
            route("::/0", "2001:db8:1::3", Some(1024), 0),
            route("::/0", "2001:db8:1::2", None, 254),
        ]);
        let err = validate_routes(&merged).unwrap_err();
        assert_eq!(err.kind(), ErrorKind::InvalidArgument);
    }

    // Same destination and (defaulted) metric but different tables must not be
    // flagged as a conflict.
    #[test]
    fn test_same_dst_different_table_no_conflict() {
        let merged = merged_for(vec![
            route("::/0", "2001:db8:1::3", None, 200),
            route("::/0", "2001:db8:1::2", None, 254),
        ]);
        validate_routes(&merged).unwrap();
    }

    // Same destination and table but distinct explicit metrics are valid.
    #[test]
    fn test_same_dst_different_metric_no_conflict() {
        let merged = merged_for(vec![
            route("::/0", "2001:db8:1::3", Some(100), 200),
            route("::/0", "2001:db8:1::2", Some(200), 200),
        ]);
        validate_routes(&merged).unwrap();
    }

    // IPv4 unset metric maps to 0, not 1024, so it must not collide with an
    // explicit metric 1024 route to the same destination.
    #[test]
    fn test_ipv4_metricless_differs_from_metric_1024() {
        let merged = merged_for(vec![
            route("0.0.0.0/0", "192.0.2.1", Some(1024), 200),
            route("0.0.0.0/0", "192.0.2.2", None, 200),
        ]);
        validate_routes(&merged).unwrap();
    }

    // The kernel coerces an explicit IPv6 metric 0 to 1024, so it conflicts
    // with a metric-less route to the same destination.
    #[test]
    fn test_ipv6_metric_zero_conflicts_with_metricless() {
        let merged = merged_for(vec![
            route("::/0", "2001:db8:1::3", Some(0), 200),
            route("::/0", "2001:db8:1::2", None, 200),
        ]);
        let err = validate_routes(&merged).unwrap_err();
        assert_eq!(err.kind(), ErrorKind::InvalidArgument);
    }
}
