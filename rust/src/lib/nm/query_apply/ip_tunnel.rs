// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::NmConnection;

pub(crate) fn is_ip_tunnel_changed(
    new_nm_conn: &NmConnection,
    cur_nm_conn: &NmConnection,
) -> bool {
    if let (Some(new_ip_tunnel_conf), Some(cur_ip_tunnel_conf)) = (
        new_nm_conn.ip_tunnel.as_ref(),
        cur_nm_conn.ip_tunnel.as_ref(),
    ) {
        new_ip_tunnel_conf.mode != cur_ip_tunnel_conf.mode
            || new_ip_tunnel_conf.parent != cur_ip_tunnel_conf.parent
            || new_ip_tunnel_conf.local != cur_ip_tunnel_conf.local
            || new_ip_tunnel_conf.remote != cur_ip_tunnel_conf.remote
            || new_ip_tunnel_conf.ttl != cur_ip_tunnel_conf.ttl
            || new_ip_tunnel_conf.tos != cur_ip_tunnel_conf.tos
            || new_ip_tunnel_conf.path_mtu_discovery
                != cur_ip_tunnel_conf.path_mtu_discovery
            || new_ip_tunnel_conf.input_key != cur_ip_tunnel_conf.input_key
            || new_ip_tunnel_conf.output_key != cur_ip_tunnel_conf.output_key
            || new_ip_tunnel_conf.encap_limit != cur_ip_tunnel_conf.encap_limit
            || new_ip_tunnel_conf.flow_label != cur_ip_tunnel_conf.flow_label
            || new_ip_tunnel_conf.fwmark != cur_ip_tunnel_conf.fwmark
            || new_ip_tunnel_conf.flags != cur_ip_tunnel_conf.flags
    } else {
        false
    }
}
