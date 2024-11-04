// SPDX-License-Identifier: Apache-2.0

use crate::{RouteEntry, RouteType};

use super::super::nm_dbus::{NmConnection, NmIpRoute};

const DEFAULT_TABLE_ID: u32 = 254; // main route table ID
const NM_EMPTY_NEXT_HOP_ADDRV4: &str = "0.0.0.0";
const NM_EMPTY_NEXT_HOP_ADDRV6: &str = "::";
const NM_DEFAULT_IPV4_METRIC: u32 = 0;

// Both `nm_dbus` are supposed to be a standalone crates,
// `RouteEntry` and `NmIpRoute` are defined outside of `nm` crate,
// Hence we cannot do `impl From<NmIpRoute> for RouteEntry` here.

fn nm_route_to_route_entry(nm_route: &NmIpRoute) -> RouteEntry {
    let mut route = RouteEntry {
        state: None,
        next_hop_iface: None,
        destination: nm_route.dest.clone(),
        next_hop_addr: {
            if let Some(next_hop) = nm_route.next_hop.as_deref() {
                if next_hop != NM_EMPTY_NEXT_HOP_ADDRV4
                    && next_hop != NM_EMPTY_NEXT_HOP_ADDRV6
                {
                    Some(next_hop.to_string())
                } else {
                    None
                }
            } else {
                None
            }
        },
        metric: nm_route.metric.as_ref().and_then(|metric| {
            if *metric == NM_DEFAULT_IPV4_METRIC {
                None
            } else {
                Some(*metric as i64)
            }
        }),
        table_id: nm_route.table.or(Some(DEFAULT_TABLE_ID)),
        weight: nm_route.weight.and_then(|weight| {
            if weight == NM_DEFAULT_IPV4_METRIC {
                None
            } else {
                Some(weight as u16)
            }
        }),
        route_type: match nm_route.route_type.as_deref() {
            Some(t) if t == RouteType::Blackhole.to_string().as_str() => {
                Some(RouteType::Blackhole)
            }
            Some(t) if t == RouteType::Unreachable.to_string().as_str() => {
                Some(RouteType::Unreachable)
            }
            Some(t) if t == RouteType::Prohibit.to_string().as_str() => {
                Some(RouteType::Unreachable)
            }
            _ => None,
        },
        cwnd: nm_route.cwnd,
        source: nm_route.src.clone(),
    };

    route.sanitize().ok();
    route
}

pub(crate) fn is_route_removed(
    new_nm_conn: &NmConnection,
    cur_nm_conn: &NmConnection,
) -> bool {
    is_nm_ip_route_removed(
        new_nm_conn
            .ipv4
            .as_ref()
            .map(|ip| ip.routes.as_slice())
            .unwrap_or(&[]),
        cur_nm_conn
            .ipv4
            .as_ref()
            .map(|ip| ip.routes.as_slice())
            .unwrap_or(&[]),
    ) || is_nm_ip_route_removed(
        new_nm_conn
            .ipv6
            .as_ref()
            .map(|ip| ip.routes.as_slice())
            .unwrap_or(&[]),
        cur_nm_conn
            .ipv6
            .as_ref()
            .map(|ip| ip.routes.as_slice())
            .unwrap_or(&[]),
    )
}

fn is_nm_ip_route_removed(
    new_routes: &[NmIpRoute],
    cur_routes: &[NmIpRoute],
) -> bool {
    let desired_routes: Vec<RouteEntry> =
        new_routes.iter().map(nm_route_to_route_entry).collect();
    let current_routes: Vec<RouteEntry> =
        cur_routes.iter().map(nm_route_to_route_entry).collect();

    for current_route in current_routes.as_slice() {
        if !desired_routes
            .iter()
            .any(|desired_route| desired_route.is_match(current_route))
        {
            return true;
        }
    }
    false
}
