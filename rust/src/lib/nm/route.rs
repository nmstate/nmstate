use log::error;
use nm_dbus::{NmConnection, NmIpRoute};

use crate::{ip::is_ipv6_addr, ErrorKind, NmstateError, RouteEntry};

pub(crate) fn gen_nm_ip_routes(
    routes: &[RouteEntry],
    is_ipv6: bool,
) -> Result<Vec<NmIpRoute>, NmstateError> {
    let mut ret = Vec::new();
    for route in routes {
        let mut nm_route = NmIpRoute::new();
        if let Some(v) = route.destination.as_ref() {
            if (is_ipv6 && !is_ipv6_addr(v)) || (!is_ipv6 && is_ipv6_addr(v)) {
                continue;
            }
            let mut splited_des: Vec<&str> = v.split('/').collect();
            splited_des.resize(2, "");
            let dest = splited_des[0];
            let prefix = if splited_des[1].is_empty() {
                if is_ipv6_addr(dest) {
                    128
                } else {
                    32
                }
            } else {
                splited_des[1].parse::<u32>().map_err(|parse_error| {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Invalid route destination {}: {}",
                            v, parse_error
                        ),
                    );
                    error!("{}", e);
                    e
                })?
            };
            nm_route.dest = Some(dest.to_string());
            nm_route.prefix = Some(prefix);
        }
        nm_route.metric = match route.metric {
            Some(RouteEntry::USE_DEFAULT_METRIC) => None,
            Some(i) => Some(i as u32),
            None => None,
        };
        nm_route.table = match route.table_id {
            Some(RouteEntry::USE_DEFAULT_ROUTE_TABLE) => None,
            Some(i) => Some(i),
            None => None,
        };
        nm_route.next_hop = route.next_hop_addr.as_ref().cloned();

        ret.push(nm_route);
    }
    Ok(ret)
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
    for cur_route in cur_routes {
        if !new_routes.contains(cur_route) {
            return true;
        }
    }
    false
}