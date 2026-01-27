// SPDX-License-Identifier: Apache-2.0

use crate::{
    IpTunnelInterface,
    ifaces::{IpTunnelConfig, IpTunnelMode},
    nm::nm_dbus::{NmConnection, NmSettingIpTunnelFlag},
};

fn tunnel_mode_to_nm(mode: IpTunnelMode) -> u32 {
    match mode {
        IpTunnelMode::Ipip => 1,
        IpTunnelMode::Sit => 3,
        IpTunnelMode::Ip6ip6 => 6,
        IpTunnelMode::Ipip6 => 7,
        _ => {
            log::warn!("Unknown IP tunnel mode: {mode:?}");
            0
        }
    }
}

fn ip_tunnel_flags_to_nm(conf: &IpTunnelConfig) -> Vec<NmSettingIpTunnelFlag> {
    let mode = conf.mode;
    if mode == Some(IpTunnelMode::Ip6ip6) || mode == Some(IpTunnelMode::Ipip6) {
        conf.ip6tun_flags
            .as_ref()
            .map(|f| f.iter().map(|f| (*f).into()).collect())
            .unwrap_or_default()
    } else {
        Vec::new()
    }
}

pub(crate) fn gen_nm_ip_tunnel_setting(
    iface: &IpTunnelInterface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_ip_tunnel_set =
        nm_conn.ip_tunnel.as_ref().cloned().unwrap_or_default();

    if let Some(ip_tunnel_conf) = iface.ip_tunnel.as_ref() {
        nm_ip_tunnel_set.mode = ip_tunnel_conf.mode.map(tunnel_mode_to_nm);
        nm_ip_tunnel_set.parent = ip_tunnel_conf.base_iface.clone();
        nm_ip_tunnel_set.local = ip_tunnel_conf.local.map(|l| l.to_string());
        nm_ip_tunnel_set.remote = ip_tunnel_conf.remote.map(|r| r.to_string());
        nm_ip_tunnel_set.ttl = ip_tunnel_conf.ttl.map(|v| v as u32);
        nm_ip_tunnel_set.tos = ip_tunnel_conf.tos.map(|v| v as u32);
        nm_ip_tunnel_set.path_mtu_discovery = ip_tunnel_conf.pmtu_disc;
        nm_ip_tunnel_set.encap_limit =
            ip_tunnel_conf.encap_limit.map(|v| v as u32);
        nm_ip_tunnel_set.flow_label = ip_tunnel_conf.flow_label;
        nm_ip_tunnel_set.fwmark = ip_tunnel_conf.fwmark;
        nm_ip_tunnel_set.flags = ip_tunnel_flags_to_nm(ip_tunnel_conf);
    }
    nm_conn.ip_tunnel = Some(nm_ip_tunnel_set);
}
