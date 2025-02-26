// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmIpRoute;

use crate::{
    ip::is_ipv6_addr, InterfaceIpAddr, NmstateError, RouteEntry, RouteType,
};

const IPV4_EMPTY_NEXT_HOP: &str = "0.0.0.0";
const IPV6_EMPTY_NEXT_HOP: &str = "::";
const IPV4_DEFAULT_METRIC: u32 = 0;
const IPV6_DEFAULT_METRIC: u32 = 1024;
const MAIN_TABLE_ID: u32 = 254;

pub(crate) fn gen_nm_ip_routes(
    routes: &[RouteEntry],
    is_ipv6: bool,
) -> Result<Vec<NmIpRoute>, NmstateError> {
    let mut ret = Vec::new();
    for route in routes {
        let mut nm_route = NmIpRoute::default();
        if let Some(v) = route.destination.as_deref() {
            if (is_ipv6 && !is_ipv6_addr(v)) || (!is_ipv6 && is_ipv6_addr(v)) {
                continue;
            }
            let ip_addr = InterfaceIpAddr::try_from(v)?;
            nm_route.prefix = Some(ip_addr.prefix_length as u32);
            nm_route.dest = Some(ip_addr.ip.to_string());
        }
        nm_route.metric = match (is_ipv6, route.metric) {
            (true, None | Some(RouteEntry::USE_DEFAULT_METRIC)) => {
                Some(IPV6_DEFAULT_METRIC)
            }
            (false, None | Some(RouteEntry::USE_DEFAULT_METRIC)) => {
                Some(IPV4_DEFAULT_METRIC)
            }
            (_, Some(i)) => Some(i as u32),
        };
        nm_route.table = match route.table_id {
            Some(RouteEntry::USE_DEFAULT_ROUTE_TABLE) => Some(MAIN_TABLE_ID),
            Some(i) => Some(i),
            None => Some(MAIN_TABLE_ID),
        };
        // Empty next-hop is represented by 0.0.0.0 or :: in nmstate, but NM and
        // the kernel just leave it undefined.
        nm_route.next_hop = route
            .next_hop_addr
            .as_ref()
            .filter(|&nh| {
                nh != IPV4_EMPTY_NEXT_HOP && nh != IPV6_EMPTY_NEXT_HOP
            })
            .cloned();
        nm_route.src = route.source.as_ref().cloned();
        if let Some(weight) = route.weight {
            nm_route.weight = Some(weight as u32);
        }
        nm_route.route_type = match route.route_type {
            Some(RouteType::Blackhole) => Some("blackhole".to_string()),
            Some(RouteType::Prohibit) => Some("prohibit".to_string()),
            Some(RouteType::Unreachable) => Some("unreachable".to_string()),
            None => None,
        };
        nm_route.cwnd = route.cwnd;
        nm_route.lock_cwnd = route.cwnd.map(|_| true);
        nm_route.initcwnd = route.initcwnd;
        nm_route.initrwnd = route.initrwnd;
        nm_route.mtu = route.mtu;
        ret.push(nm_route);
    }
    Ok(ret)
}
