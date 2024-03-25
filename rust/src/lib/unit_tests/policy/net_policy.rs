// SPDX-License-Identifier: Apache-2.0

use std::str::FromStr;

use crate::{NetworkPolicy, NetworkState};

#[test]
fn test_policy_move_dhcp_gw_eth_to_bridge() {
    let mut policy: NetworkPolicy = serde_yaml::from_str(
        r#"
capture:
  gw: routes.running.destination=="0.0.0.0/0"
  base-iface: >-
    interfaces.name==capture.gw.routes.running.0.next-hop-interface
desiredState:
  interfaces:
  - name: br1
    type: linux-bridge
    state: up
    mac-address: "{{ capture.base-iface.interfaces.0.mac-address }}"
    ipv4:
      dhcp: true
      enabled: true
    bridge:
        port:
        - name: "{{ capture.base-iface.interfaces.0.name }}"
        "#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            mac-address: 11:22:33:44:55:66
            ipv4:
              dhcp: true
              enabled: true

        routes:
          running:
          - destination: 0.0.0.0/0
            next-hop-address: 192.0.2.1
            next-hop-interface: eth1
          config: []
        ",
    )
    .unwrap();

    policy.current = Some(current);

    let state = NetworkState::try_from(policy).unwrap();

    let ifaces = state.interfaces.to_vec();
    assert_eq!(ifaces.len(), 1);
    assert_eq!(ifaces[0].name(), "br1");
    assert_eq!(ifaces[0].ports(), Some(vec!["eth1"]));
    assert_eq!(
        ifaces[0].base_iface().mac_address,
        Some("11:22:33:44:55:66".to_string())
    );
}

#[test]
fn test_policy_move_static_gw_eth_to_bridge() {
    let mut policy: NetworkPolicy = serde_yaml::from_str(
        r#"
capture:
  void: this capture will just clone current without modification
  default-gw: routes.running.destination=="0.0.0.0/0"
  base-iface: >-
    interfaces.name==
    capture.default-gw.routes.running.0.next-hop-interface
  base-iface-routes: >-
    routes.running.next-hop-interface==
    capture.default-gw.routes.running.0.next-hop-interface
  bridge-routes: >-
    capture.base-iface-routes | routes.running.next-hop-interface:="br1"
desiredState:
  interfaces:
  - name: br1
    description: Linux bridge with base interface as a port
    type: linux-bridge
    state: up
    ipv4: "{{ capture.base-iface.interfaces.0.ipv4 }}"
    bridge:
      options:
        stp:
          enabled: false
      port:
      - name: "{{ capture.base-iface.interfaces.0.name }}"
  routes:
    config: "{{ capture.bridge-routes.routes.running }}"
        "#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            mac-address: 11:22:33:44:55:66
            ipv4:
              address:
              - ip: 192.0.2.251
                prefix-length: 24
              dhcp: false
              enabled: true
        routes:
          config:
          - destination: 0.0.0.0/0
            next-hop-address: 192.0.2.1
            next-hop-interface: eth1
          - destination: 192.51.100.0/24
            next-hop-address: 192.0.2.1
            next-hop-interface: eth1
          running:
          - destination: 0.0.0.0/0
            next-hop-address: 192.0.2.1
            next-hop-interface: eth1
          - destination: 192.51.100.0/24
            next-hop-address: 192.0.2.1
            next-hop-interface: eth1
        ",
    )
    .unwrap();

    policy.current = Some(current);

    let state = NetworkState::try_from(policy).unwrap();

    let ifaces = state.interfaces.to_vec();
    assert_eq!(ifaces.len(), 1);
    assert_eq!(ifaces[0].name(), "br1");
    assert_eq!(ifaces[0].ports(), Some(vec!["eth1"]));
    assert!(ifaces[0].base_iface().ipv4.as_ref().unwrap().enabled);
    let ip_addrs = ifaces[0]
        .base_iface()
        .ipv4
        .as_ref()
        .unwrap()
        .addresses
        .as_ref()
        .unwrap();
    assert_eq!(ip_addrs.len(), 1);
    assert_eq!(
        ip_addrs[0].ip,
        std::net::IpAddr::from_str("192.0.2.251").unwrap()
    );
    let routes = state.routes.config.as_ref().unwrap();
    assert_eq!(routes.len(), 2);
    assert_eq!(routes[0].destination, Some("0.0.0.0/0".to_string()));
    assert_eq!(routes[0].next_hop_iface, Some("br1".to_string()));
    assert_eq!(routes[1].destination, Some("192.51.100.0/24".to_string()));
    assert_eq!(routes[1].next_hop_iface, Some("br1".to_string()));
}

#[test]
fn test_policy_convert_dhcp_to_static_with_dns() {
    let mut policy: NetworkPolicy = serde_yaml::from_str(
        r#"
        capture:
          eth1-iface: interfaces.name == "eth1"
          eth1-routes: routes.running.next-hop-interface == "eth1"
          dns: dns-resolver.running
        desiredState:
          interfaces:
          - name: eth1
            type: ethernet
            state: up
            ipv4:
              address: "{{ capture.eth1-iface.interfaces.0.ipv4.address }}"
              dhcp: false
              enabled: true
          routes:
            config: "{{ capture.eth1-routes.routes.running }}"
          dns-resolver:
            config: "{{ capture.dns.dns-resolver.running }}"
        "#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            mac-address: 11:22:33:44:55:66
            ipv4:
              address:
              - ip: 192.0.2.251
                prefix-length: 24
              dhcp: true
              enabled: true
        routes:
          running:
          - destination: 0.0.0.0/0
            next-hop-address: 192.0.2.1
            next-hop-interface: eth1
          - destination: 192.51.100.0/24
            next-hop-address: 192.0.2.1
            next-hop-interface: eth1
        dns-resolver:
          running:
            search:
            - example.com
            - example.org
            server:
            - 192.51.100.99
            - 2001:db8:1::99
        ",
    )
    .unwrap();

    policy.current = Some(current);

    let state = NetworkState::try_from(policy).unwrap();

    let ifaces = state.interfaces.to_vec();
    assert_eq!(ifaces.len(), 1);
    assert_eq!(ifaces[0].name(), "eth1");
    assert!(
        !(*ifaces[0]
            .base_iface()
            .ipv4
            .as_ref()
            .unwrap()
            .dhcp
            .as_ref()
            .unwrap())
    );
    let routes = state.routes.config.as_ref().unwrap();
    assert_eq!(routes.len(), 2);
    assert_eq!(routes[0].destination, Some("0.0.0.0/0".to_string()));
    assert_eq!(routes[0].next_hop_iface, Some("eth1".to_string()));
    assert_eq!(routes[1].destination, Some("192.51.100.0/24".to_string()));
    assert_eq!(routes[1].next_hop_iface, Some("eth1".to_string()));
    let dns_config =
        state.dns.as_ref().and_then(|d| d.config.as_ref()).unwrap();
    assert_eq!(
        dns_config.server,
        Some(vec![
            "192.51.100.99".to_string(),
            "2001:db8:1::99".to_string()
        ])
    );
    assert_eq!(
        dns_config.search,
        Some(vec!["example.com".to_string(), "example.org".to_string()])
    );
}

#[test]
fn test_policy_empty_policy() {
    let policy: NetworkPolicy = serde_yaml::from_str("").unwrap();
    let state = NetworkState::try_from(policy).unwrap();
    assert_eq!(state, NetworkState::new());
}

#[test]
fn test_policy_no_capture() {
    let policy: NetworkPolicy = serde_yaml::from_str(
        r"
        desiredState:
          interfaces:
          - name: eth1
            type: ethernet
            state: up
        ",
    )
    .unwrap();

    let state = NetworkState::try_from(policy).unwrap();
    let expected_state: NetworkState = serde_yaml::from_str(
        r"
        interfaces:
          - name: eth1
            type: ethernet
            state: up
        ",
    )
    .unwrap();
    assert_eq!(state, expected_state);
}
