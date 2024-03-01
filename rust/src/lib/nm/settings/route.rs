// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmIpRoute;

use crate::{
    ip::is_ipv6_addr, InterfaceIpAddr, NmstateError, RouteEntry, RouteType,
};

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
        nm_route.metric = match route.metric {
            Some(RouteEntry::USE_DEFAULT_METRIC) => Some(0),
            Some(i) => Some(i as u32),
            None => Some(0),
        };
        nm_route.table = match route.table_id {
            Some(RouteEntry::USE_DEFAULT_ROUTE_TABLE) => None,
            Some(i) => Some(i),
            None => None,
        };
        nm_route.next_hop = route.next_hop_addr.as_ref().cloned();
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
        ret.push(nm_route);
    }
    Ok(ret)
}
