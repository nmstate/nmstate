// SPDX-License-Identifier: Apache-2.0

use crate::{MergedInterface, MergedNetworkState, NmstateError, RouteEntry};
#[cfg(feature = "query_apply")]
use crate::{RouteType, route::reconcile_saved_static_routes};

pub(crate) fn store_route_config(
    merged_state: &mut MergedNetworkState,
) -> Result<(), NmstateError> {
    if merged_state.routes.is_changed() {
        let empty_rts = Vec::new();
        for iface_name in merged_state.routes.route_changed_ifaces.as_slice() {
            let rts =
                if let Some(rts) = merged_state.routes.merged.get(iface_name) {
                    rts
                } else {
                    &empty_rts
                };
            if let Some(iface) =
                merged_state.interfaces.kernel_ifaces.get_mut(iface_name)
            {
                assign_iface_routes(iface, rts);
            }
        }
    }
    Ok(())
}

/// Rewrite saved NetworkManager routes that an authoritative scope owns when
/// the kernel no longer has them. Routes outside the scope stay in the
/// profile, including a default gateway stored separately from the route list.
#[cfg(feature = "query_apply")]
pub(crate) fn store_saved_routes_for_authoritative_scope(
    merged_state: &mut MergedNetworkState,
    conn_matcher: &super::NmConnectionMatcher,
) -> Result<(), NmstateError> {
    let scopes = merged_state
        .routes
        .desired
        .authoritative
        .clone()
        .unwrap_or_default();
    if scopes.is_empty() {
        return Ok(());
    }
    let desired_routes = merged_state
        .routes
        .desired
        .config
        .clone()
        .unwrap_or_default();
    let iface_names: Vec<String> = merged_state
        .interfaces
        .kernel_ifaces
        .keys()
        .cloned()
        .collect();

    for iface_name in iface_names {
        if merged_state.interfaces.ignored_ifaces.iter().any(
            |(name, iface_type)| {
                name == &iface_name && !iface_type.is_userspace()
            },
        ) {
            continue;
        }
        let Some(iface) =
            merged_state.interfaces.kernel_ifaces.get(&iface_name)
        else {
            continue;
        };
        let Some(saved_conn) =
            conn_matcher.get_prefered_saved(iface.merged.base_iface())
        else {
            continue;
        };
        let saved_routes = nm_conn_to_route_entries(saved_conn, &iface_name);
        if saved_routes.is_empty() {
            continue;
        }
        let merged_iface_routes = merged_state
            .routes
            .merged
            .get(&iface_name)
            .cloned()
            .unwrap_or_default();
        let iface_routes_changed = merged_state
            .routes
            .route_changed_ifaces
            .iter()
            .any(|name| name == &iface_name);
        let Some(routes) = reconcile_saved_static_routes(
            scopes.as_slice(),
            desired_routes.as_slice(),
            saved_routes.as_slice(),
            merged_iface_routes.as_slice(),
            iface_routes_changed,
        ) else {
            continue;
        };
        if let Some(iface) =
            merged_state.interfaces.kernel_ifaces.get_mut(&iface_name)
        {
            assign_iface_routes(iface, routes.as_slice());
        }
    }
    Ok(())
}

fn assign_iface_routes(iface: &mut MergedInterface, routes: &[RouteEntry]) {
    if !iface.is_changed() {
        iface.mark_as_changed();
    }
    let Some(apply_iface) = iface.for_apply.as_mut() else {
        return;
    };
    if apply_iface.base_iface_mut().ipv4.is_none() {
        apply_iface
            .base_iface_mut()
            .ipv4
            .clone_from(&iface.merged.base_iface_mut().ipv4);
        if let Some(addrs) = apply_iface
            .base_iface_mut()
            .ipv4
            .as_mut()
            .and_then(|ip| ip.addresses.as_mut())
        {
            addrs.retain(|addr| !addr.is_protocol_other());
        }
    }
    if apply_iface.base_iface_mut().ipv6.is_none() {
        apply_iface
            .base_iface_mut()
            .ipv6
            .clone_from(&iface.merged.base_iface_mut().ipv6);
        if let Some(addrs) = apply_iface
            .base_iface_mut()
            .ipv6
            .as_mut()
            .and_then(|ip| ip.addresses.as_mut())
        {
            addrs.retain(|addr| !addr.is_protocol_other());
        }
    }
    apply_iface.base_iface_mut().routes = Some(routes.to_vec());
}

#[cfg(feature = "query_apply")]
fn nm_conn_to_route_entries(
    conn: &super::nm_dbus::NmConnection,
    iface_name: &str,
) -> Vec<RouteEntry> {
    let mut routes = Vec::new();
    if let Some(ipv4) = conn.ipv4.as_ref() {
        for route in &ipv4.routes {
            if let Some(entry) = nm_ip_route_to_route_entry(route, iface_name) {
                routes.push(entry);
            }
        }
        if let Some(gateway) = ipv4.gateway.as_deref() {
            append_nm_gateway(
                &mut routes,
                gateway,
                ipv4.route_table,
                ipv4.route_metric,
                iface_name,
                false,
            );
        }
    }
    if let Some(ipv6) = conn.ipv6.as_ref() {
        for route in &ipv6.routes {
            if let Some(entry) = nm_ip_route_to_route_entry(route, iface_name) {
                routes.push(entry);
            }
        }
        if let Some(gateway) = ipv6.gateway.as_deref() {
            append_nm_gateway(
                &mut routes,
                gateway,
                ipv6.route_table,
                ipv6.route_metric,
                iface_name,
                true,
            );
        }
    }
    routes
}

#[cfg(feature = "query_apply")]
fn nm_ip_route_to_route_entry(
    route: &super::nm_dbus::NmIpRoute,
    iface_name: &str,
) -> Option<RouteEntry> {
    let destination = match (route.dest.as_deref(), route.prefix) {
        (Some(dest), Some(prefix)) => Some(format!("{dest}/{prefix}")),
        (Some(dest), None) => Some(dest.to_string()),
        _ => None,
    }?;
    let mut entry = RouteEntry::new();
    entry.destination = Some(destination);
    entry.next_hop_addr = route.next_hop.clone();
    entry.source = route.src.clone();
    entry.table_id = route.table;
    entry.metric = route.metric.map(i64::from);
    entry.weight = route.weight.and_then(|weight| u16::try_from(weight).ok());
    entry.route_type = match route.route_type.as_deref() {
        Some("blackhole") => Some(RouteType::Blackhole),
        Some("unreachable") => Some(RouteType::Unreachable),
        Some("prohibit") => Some(RouteType::Prohibit),
        _ => None,
    };
    if entry.is_unicast() {
        entry.next_hop_iface = Some(iface_name.to_string());
    }
    entry.cwnd = route.cwnd;
    entry.initcwnd = route.initcwnd;
    entry.initrwnd = route.initrwnd;
    entry.mtu = route.mtu;
    entry.quickack = route.quickack;
    entry.advmss = route.advmss;
    entry.lock_mtu = route.lock_mtu;
    let _ = entry.sanitize();
    Some(entry)
}

#[cfg(feature = "query_apply")]
fn append_nm_gateway(
    routes: &mut Vec<RouteEntry>,
    gateway: &str,
    table: Option<u32>,
    metric: Option<i64>,
    iface_name: &str,
    is_ipv6: bool,
) {
    let destination = if is_ipv6 { "::/0" } else { "0.0.0.0/0" };
    if routes.iter().any(|route| {
        route.destination.as_deref() == Some(destination)
            && route.next_hop_addr.as_deref() == Some(gateway)
    }) {
        return;
    }
    let mut route = RouteEntry::new();
    route.destination = Some(destination.to_string());
    route.next_hop_addr = Some(gateway.to_string());
    route.next_hop_iface = Some(iface_name.to_string());
    route.table_id = table.filter(|table_id| *table_id != 0);
    route.metric = metric;
    routes.push(route);
}

#[cfg(all(test, feature = "query_apply"))]
mod tests {
    use super::*;
    use crate::{
        NetworkState,
        nm::{
            NmConnectionMatcher,
            nm_dbus::{
                NmConnection, NmIfaceType, NmIpRoute, NmSettingConnection,
                NmSettingIp,
            },
        },
    };

    fn nm_route(
        dest: &str,
        prefix: u32,
        next_hop: &str,
        table: u32,
    ) -> NmIpRoute {
        let mut route = NmIpRoute::default();
        route.dest = Some(dest.to_string());
        route.prefix = Some(prefix);
        route.next_hop = Some(next_hop.to_string());
        route.table = Some(table);
        route.metric = Some(100);
        route
    }

    fn saved_conn(iface_name: &str, routes: Vec<NmIpRoute>) -> NmConnection {
        let mut conn = NmConnection::default();
        let mut connection = NmSettingConnection::default();
        connection.id = Some(iface_name.to_string());
        connection.uuid = Some(match iface_name {
            "eth1" => "aaaaaaaa-aaaa-aaaa-aaaa-000000000001".to_string(),
            _ => "aaaaaaaa-aaaa-aaaa-aaaa-000000000002".to_string(),
        });
        connection.iface_type = Some(NmIfaceType::Ethernet);
        connection.iface_name = Some(iface_name.to_string());
        conn.connection = Some(connection);
        let mut ipv4 = NmSettingIp::default();
        ipv4.routes = routes;
        if iface_name == "eth1" {
            // Gateway lives in table 100, outside the table 254 scope.
            ipv4.gateway = Some("192.0.2.1".to_string());
            ipv4.route_table = Some(100);
        }
        conn.ipv4 = Some(ipv4);
        conn
    }

    #[test]
    fn test_authoritative_scope_reconciles_saved_routes_missing_from_kernel() {
        let current: NetworkState = serde_yaml::from_str(
            r#"
            interfaces:
            - name: eth1
              type: ethernet
              state: up
              ipv4:
                enabled: true
                dhcp: false
                address:
                - ip: 192.0.2.251
                  prefix-length: 24
            - name: eth2
              type: ethernet
              state: up
              ipv4:
                enabled: true
                dhcp: false
                address:
                - ip: 198.51.100.251
                  prefix-length: 24
            "#,
        )
        .unwrap();
        let desired: NetworkState = serde_yaml::from_str(
            r#"
            routes:
              authoritative:
              - table-id: 254
              config: []
            "#,
        )
        .unwrap();
        let mut merged = MergedNetworkState::new(
            desired,
            current,
            Default::default(),
            false,
        )
        .unwrap();
        let matcher = NmConnectionMatcher::new(
            vec![
                saved_conn(
                    "eth1",
                    vec![
                        nm_route("198.51.100.0", 24, "192.0.2.1", 254),
                        nm_route("203.0.113.0", 24, "192.0.2.1", 100),
                    ],
                ),
                saved_conn(
                    "eth2",
                    vec![nm_route("203.0.113.0", 24, "198.51.100.1", 254)],
                ),
            ],
            Vec::new(),
            Vec::new(),
            &merged.interfaces,
        );

        store_saved_routes_for_authoritative_scope(&mut merged, &matcher)
            .unwrap();

        let eth1_routes = merged
            .interfaces
            .kernel_ifaces
            .get("eth1")
            .unwrap()
            .for_apply
            .as_ref()
            .unwrap()
            .base_iface()
            .routes
            .as_ref()
            .unwrap();
        assert!(
            eth1_routes.iter().any(|route| {
                route.destination.as_deref() == Some("203.0.113.0/24")
                    && route.table_id == Some(100)
            }),
            "saved route outside the table scope should stay: {eth1_routes:?}"
        );
        assert!(
            eth1_routes.iter().any(|route| {
                route.destination.as_deref() == Some("0.0.0.0/0")
                    && route.next_hop_addr.as_deref() == Some("192.0.2.1")
                    && route.table_id == Some(100)
            }),
            "gateway outside the table scope should stay: {eth1_routes:?}"
        );
        assert!(
            !eth1_routes
                .iter()
                .any(|route| route.destination.as_deref()
                    == Some("198.51.100.0/24")),
            "stale in-scope saved route should be removed: {eth1_routes:?}"
        );

        let eth2_routes = merged
            .interfaces
            .kernel_ifaces
            .get("eth2")
            .unwrap()
            .for_apply
            .as_ref()
            .unwrap()
            .base_iface()
            .routes
            .as_ref()
            .unwrap();
        assert!(
            eth2_routes.is_empty(),
            "eth2's only saved route is in the scope: {eth2_routes:?}"
        );
    }
}
