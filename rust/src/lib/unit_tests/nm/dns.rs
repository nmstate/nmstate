// SPDX-License-Identifier: Apache-2.0

use crate::{
    nm::dns::store_dns_config_to_iface, DnsClientState, ErrorKind,
    InterfaceType, MergedNetworkState, NetworkState,
};

#[test]
fn test_dns_ignore_dns_purge_on_absent_iface() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
dns-resolver:
  config:
    server: []
interfaces:
  - name: dummy0
    type: dummy
    state: absent
"#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r#"---
dns-resolver:
  config:
    search:
    - example.com
    - example.org
    server:
    - 8.8.8.8
    - 2001:4860:4860::8888
interfaces:
  - name: dummy0
    type: dummy
    state: up
    ipv4:
      enabled: true
      dhcp: true
      auto-dns: false
    ipv6:
      enabled: true
      dhcp: true
      autoconf: true
      auto-dns: false
"#,
    )
    .unwrap();

    let mut merged_state =
        MergedNetworkState::new(desired, current, false, false).unwrap();

    store_dns_config_to_iface(&mut merged_state).unwrap();

    let iface = merged_state
        .interfaces
        .get_iface("dummy0", InterfaceType::Dummy)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert!(iface.is_absent());
}

#[test]
fn test_dns_ipv6_link_local_iface_has_ipv6_disabled() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        dns-resolver:
          config:
            server:
            - fe80::deef:1%eth1
        "#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r#"---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            ipv6:
              enabled: false
        "#,
    )
    .unwrap();

    let result = MergedNetworkState::new(desired, current, false, false);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_two_dns_ipv6_link_local_iface() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        dns-resolver:
          config:
            server:
            - fe80::deef:1%eth1
            - fe80::deef:2%eth2
        "#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r#"---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            ipv6:
              enabled: true
              dhcp: true
              autoconf: true
              auto-dns: false
          - name: eth2
            type: ethernet
            state: up
            ipv6:
              enabled: true
              dhcp: true
              autoconf: true
              auto-dns: false
        "#,
    )
    .unwrap();
    let result = MergedNetworkState::new(desired, current, false, false);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::NotImplementedError);
    }
}

#[test]
fn test_dns_iface_has_no_ip_stack_info() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        interfaces:
          - name: eth1
        "#,
    )
    .unwrap();
    let mut current: NetworkState = serde_yaml::from_str(
        r#"---
        dns-resolver:
          config:
            search:
            - example.com
            - example.org
            server:
            - 2001:db8:f::1
            - 2001:db8:f::2
            - 192.0.2.250
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            ipv4:
              address:
              - ip: 192.0.2.251
                prefix-length: 24
              dhcp: false
              enabled: true
            ipv6:
              address:
              - ip: 2001:db8:1::1
                prefix-length: 64
              dhcp: false
              enabled: true
              autoconf: false
        routes:
          config:
          - destination: 0.0.0.0/0
            next-hop-address: 192.0.2.1
            next-hop-interface: eth1
          - destination: ::/0
            next-hop-address: 2001:db8:1::3
            next-hop-interface: eth1
        "#,
    )
    .unwrap();
    if let Some(ip) = current
        .interfaces
        .kernel_ifaces
        .get_mut("eth1")
        .unwrap()
        .base_iface_mut()
        .ipv4
        .as_mut()
    {
        ip.dns = Some({
            DnsClientState {
                server: Some(vec!["192.0.2.250".to_string()]),
                priority: Some(100),
                ..Default::default()
            }
        })
    };
    if let Some(ip) = current
        .interfaces
        .kernel_ifaces
        .get_mut("eth1")
        .unwrap()
        .base_iface_mut()
        .ipv6
        .as_mut()
    {
        ip.dns = Some({
            DnsClientState {
                server: Some(vec![
                    "2001:db8:f::1".to_string(),
                    "2001:db8:f::2".to_string(),
                ]),
                search: Some(vec![
                    "example.com".to_string(),
                    "example.org".to_string(),
                ]),
                priority: Some(10),
            }
        })
    };
    let mut merged_state =
        MergedNetworkState::new(desired, current, false, false).unwrap();

    store_dns_config_to_iface(&mut merged_state).unwrap();
}
