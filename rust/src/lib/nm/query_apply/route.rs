// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{NmConnection, NmIpRoute};

const DEFAULT_TABLE_ID: u32 = 254; // main route table ID

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
        let mut cur_route_norm = cur_route.clone();
        if cur_route_norm.table.is_none() {
            cur_route_norm.table = Some(DEFAULT_TABLE_ID);
        }
        if !new_routes.contains(&cur_route_norm) {
            return true;
        }
    }
    false
}
