// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, NetworkState};

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
    let (_, chg_state, del_state) =
        desired.gen_state_for_apply(&current).unwrap();

    assert!(chg_state.interfaces.to_vec().is_empty());
    let iface = del_state.interfaces.to_vec()[0];
    assert_eq!(iface.name(), "dummy0");
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
    let result = desired.gen_state_for_apply(&current);
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
    let result = desired.gen_state_for_apply(&current);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::NotImplementedError);
    }
}
