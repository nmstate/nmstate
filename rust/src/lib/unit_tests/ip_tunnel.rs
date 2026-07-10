// SPDX-License-Identifier: Apache-2.0

use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};

use crate::{
    ErrorKind, Interfaces, IpTunnelInterface, MergedInterfaces,
    ifaces::{Ip6TunnelFlag, IpTunnelMode},
};

#[test]
fn test_ipip_tunnel_config() {
    let iface: IpTunnelInterface = serde_yaml::from_str(
        r"---
name: ipip0
type: ip-tunnel
state: up
ip-tunnel:
  mode: ipip
  local: 192.0.2.1
  remote: 192.0.2.2
  ttl: 255",
    )
    .unwrap();

    let tun = iface.ip_tunnel.unwrap();

    assert_eq!(tun.ttl, Some(255));
    assert_eq!(tun.local, Some(IpAddr::V4(Ipv4Addr::new(192, 0, 2, 1))));
    assert_eq!(tun.remote, Some(IpAddr::V4(Ipv4Addr::new(192, 0, 2, 2))));
    assert_eq!(tun.mode, Some(IpTunnelMode::Ipip));
}

#[test]
fn test_ipip6_with_flags() {
    let mut iface: IpTunnelInterface = serde_yaml::from_str(
        r"---
name: ipip60
type: ip-tunnel
state: up
ip-tunnel:
  mode: ipip6
  local: 2001:db8::ffff
  remote: 2001:db8::1
  ttl: 255
  ip6tun-flags:
   - use-orig-tclass
   - ign-encap-limit
   - use-orig-flowlabel
   - mip6-dev
        ",
    )
    .unwrap();

    iface.sanitize_desired_for_verify();

    let tun = iface.ip_tunnel.unwrap();

    assert_eq!(
        tun.ip6tun_flags,
        Some(vec![
            Ip6TunnelFlag::IgnEncapLimit,
            Ip6TunnelFlag::UseOrigTclass,
            Ip6TunnelFlag::UseOrigFlowlabel,
            Ip6TunnelFlag::Mip6Dev,
        ])
    );
    assert_eq!(tun.ttl, Some(255));
    assert_eq!(
        tun.local,
        Some(IpAddr::V6(Ipv6Addr::new(
            0x2001, 0xdb8, 0, 0, 0, 0, 0, 0xffff
        )))
    );
    assert_eq!(
        tun.remote,
        Some(IpAddr::V6(Ipv6Addr::new(0x2001, 0xdb8, 0, 0, 0, 0, 0, 0x1)))
    );
    assert_eq!(tun.mode, Some(IpTunnelMode::Ipip6));
}

#[test]
fn test_sit_with_encap_and_ip6tun_flags() {
    let mut iface: IpTunnelInterface = serde_yaml::from_str(
        r"---
name: sit0
type: ip-tunnel
state: up
ip-tunnel:
  mode: sit
  local: 192.0.2.1
  remote: 192.0.2.2
  ttl: 255",
    )
    .unwrap();

    iface.sanitize_desired_for_verify();

    let tun = iface.ip_tunnel.unwrap();

    assert_eq!(tun.ttl, Some(255));
    assert_eq!(tun.local, Some(IpAddr::V4(Ipv4Addr::new(192, 0, 2, 1))));
    assert_eq!(tun.remote, Some(IpAddr::V4(Ipv4Addr::new(192, 0, 2, 2))));
    assert_eq!(tun.mode, Some(IpTunnelMode::Sit));
}

#[test]
fn test_reject_invalid_flow_label() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: ipip0
  type: ip-tunnel
  state: up
  ip-tunnel:
    mode: ipip
    local: 192.0.2.1
    remote: 192.0.2.2
    ttl: 255
    flow-label: 0x100000",
    )
    .unwrap();

    let err = MergedInterfaces::new(
        des_ifaces,
        Interfaces::new(),
        Default::default(),
        false,
    )
    .unwrap_err();

    assert_eq!(err.kind(), ErrorKind::InvalidArgument);
    assert!(err.msg().contains("Flow label"));
}

#[test]
fn test_ip_tunnel_deny_unknown_config_field() {
    let result = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: ipip0
          type: ip-tunnel
          state: up
          ip-tunnel:
            mode: ipip
            local: 192.0.2.1
            remotee: 192.0.2.2
        ",
    );
    let err = result.unwrap_err().to_string();
    assert!(err.contains("unknown field"));
    assert!(err.contains("remotee"));
}
