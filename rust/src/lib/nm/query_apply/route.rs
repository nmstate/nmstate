// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{NmConnection, NmIpRoute, NmSettingIp};

const NM_IP_SETTING_ROUTE_TABLE_DEFAULT: u32 = 0;
const NM_IP_SETTING_ROUTE_METRIC_DEFAULT: i64 = -1;
const IPV6_METRIC_COHERCED_DEFAULT: u32 = 1024; // Coherced by kernel 0->1024

pub(crate) fn is_route_removed(
    new_nm_conn: &NmConnection,
    cur_nm_conn: &NmConnection,
) -> bool {
    nm_setting_is_route_removed(
        new_nm_conn.ipv4.as_ref(),
        cur_nm_conn.ipv4.as_ref(),
        false,
    ) || nm_setting_is_route_removed(
        new_nm_conn.ipv6.as_ref(),
        cur_nm_conn.ipv6.as_ref(),
        true,
    )
}

/// Return true when ipv4/ipv6.route-table differs between connections.
///
/// Missing route-table and route-table=0 are treated as equal defaults so
/// representation-only differences do not force a deactivate/reactivate.
/// parse_dhcp_opts() also maps a missing value to 0.
pub(crate) fn is_route_table_changed(
    new_nm_conn: &NmConnection,
    cur_nm_conn: &NmConnection,
) -> bool {
    is_nm_ip_route_table_changed(
        new_nm_conn.ipv4.as_ref(),
        cur_nm_conn.ipv4.as_ref(),
    ) || is_nm_ip_route_table_changed(
        new_nm_conn.ipv6.as_ref(),
        cur_nm_conn.ipv6.as_ref(),
    )
}

/// Compare one address-family route-table after normalizing NM defaults.
fn is_nm_ip_route_table_changed(
    new_nm_sett: Option<&NmSettingIp>,
    cur_nm_sett: Option<&NmSettingIp>,
) -> bool {
    if let (Some(new_nm_sett), Some(cur_nm_sett)) = (new_nm_sett, cur_nm_sett) {
        normalize_nm_route_table(new_nm_sett.route_table)
            != normalize_nm_route_table(cur_nm_sett.route_table)
    } else {
        false
    }
}

/// Map NM route-table values so unset and 0 both mean the default table.
fn normalize_nm_route_table(route_table: Option<u32>) -> u32 {
    route_table.unwrap_or(NM_IP_SETTING_ROUTE_TABLE_DEFAULT)
}

fn nm_setting_is_route_removed(
    new_nm_sett: Option<&NmSettingIp>,
    cur_nm_sett: Option<&NmSettingIp>,
    is_ipv6: bool,
) -> bool {
    let new_routes = clone_normalized_routes(new_nm_sett, is_ipv6);
    let cur_routes = clone_normalized_routes(cur_nm_sett, is_ipv6);
    cur_routes
        .iter()
        .any(|cur_route| !new_routes.contains(cur_route))
}

fn clone_normalized_routes(
    ip_sett: Option<&NmSettingIp>,
    is_ipv6: bool,
) -> Vec<NmIpRoute> {
    // Routes defined by nmstate will always has table and metric set, so there
    // is no problem comparing them.
    // On routes defined in NM directly, they may depend on the route-metric and
    // route-table properties of the ipv4 and ipv6 settings. Use them to get the
    // actual values.
    // They may even fall back to a globally default value. In that case we can
    // not know what value is. Use None to fail the comparison so we can
    // properly install the new desired route, with table and metric defined.
    let default_table = ip_sett
        .and_then(|ip| ip.route_table)
        .filter(|tbl| *tbl != NM_IP_SETTING_ROUTE_TABLE_DEFAULT);
    let mut default_metric = ip_sett
        .and_then(|ip| ip.route_metric)
        .filter(|mtr| *mtr != NM_IP_SETTING_ROUTE_METRIC_DEFAULT)
        .map(|mtr| mtr as u32);
    if is_ipv6 && default_metric == Some(0) {
        default_metric = Some(IPV6_METRIC_COHERCED_DEFAULT);
    }

    let routes = ip_sett.map(|ip| ip.routes.as_slice()).unwrap_or(&[]);
    routes
        .iter()
        .map(|rt| {
            let mut new_rt = rt.clone();
            new_rt.table = rt.table.or(default_table);
            new_rt.metric = rt.metric.or(default_metric);
            new_rt
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::{
        NmConnection, NmSettingIp, is_route_table_changed,
        normalize_nm_route_table,
    };

    /// Missing and explicit 0 both normalize to the default table.
    #[test]
    fn test_normalize_nm_route_table_treats_missing_as_default() {
        assert_eq!(normalize_nm_route_table(None), 0);
        assert_eq!(normalize_nm_route_table(Some(0)), 0);
        assert_eq!(normalize_nm_route_table(Some(1000)), 1000);
    }

    /// None vs Some(0) must not be treated as a route-table change.
    #[test]
    fn test_is_route_table_changed_ignores_default_representation() {
        let mut new_nm_sett = NmSettingIp::default();
        new_nm_sett.route_table = None;
        let mut cur_nm_sett = NmSettingIp::default();
        cur_nm_sett.route_table = Some(0);

        let mut new_nm_conn = NmConnection::default();
        new_nm_conn.ipv6 = Some(new_nm_sett);
        let mut cur_nm_conn = NmConnection::default();
        cur_nm_conn.ipv6 = Some(cur_nm_sett);

        assert!(!is_route_table_changed(&new_nm_conn, &cur_nm_conn));
    }

    /// Changing auto-route-table-id from 1000 to 2000 is a real change.
    #[test]
    fn test_is_route_table_changed_detects_table_id_change() {
        let mut new_nm_sett = NmSettingIp::default();
        new_nm_sett.route_table = Some(2000);
        let mut cur_nm_sett = NmSettingIp::default();
        cur_nm_sett.route_table = Some(1000);

        let mut new_nm_conn = NmConnection::default();
        new_nm_conn.ipv6 = Some(new_nm_sett);
        let mut cur_nm_conn = NmConnection::default();
        cur_nm_conn.ipv6 = Some(cur_nm_sett);

        assert!(is_route_table_changed(&new_nm_conn, &cur_nm_conn));
    }

    /// IPv4-only auto-route-table-id 1000 to 2000 is also a real change.
    #[test]
    fn test_is_route_table_changed_detects_ipv4_table_id_change() {
        let mut new_nm_sett = NmSettingIp::default();
        new_nm_sett.route_table = Some(2000);
        let mut cur_nm_sett = NmSettingIp::default();
        cur_nm_sett.route_table = Some(1000);

        let mut new_nm_conn = NmConnection::default();
        new_nm_conn.ipv4 = Some(new_nm_sett);
        let mut cur_nm_conn = NmConnection::default();
        cur_nm_conn.ipv4 = Some(cur_nm_sett);

        assert!(is_route_table_changed(&new_nm_conn, &cur_nm_conn));
    }
}
