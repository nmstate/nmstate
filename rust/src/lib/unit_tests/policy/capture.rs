// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{
    policy::{
        capture::{NetworkCaptureAction, NetworkCaptureCommand},
        token::NetworkCaptureToken,
    },
    NetworkState,
};

#[test]
fn test_policy_capture_with_replace() {
    let cap_con = NetworkCaptureCommand::parse(
        r#"
        capture.base-iface-routes | routes.running.next-hop-interface:="br1"
        "#
        .trim(),
    )
    .unwrap();

    assert_eq!(
        cap_con.key_capture.as_ref(),
        Some(&"base-iface-routes".to_string())
    );
    assert_eq!(cap_con.action, NetworkCaptureAction::Replace);
    assert_eq!(
        cap_con.key,
        NetworkCaptureToken::Path(
            vec![
                "routes".to_string(),
                "running".to_string(),
                "next-hop-interface".to_string(),
            ],
            "capture.base-iface-routes | r".len() - 1,
        )
    );
    assert_eq!(
        cap_con.value,
        NetworkCaptureToken::Value(
            "br1".to_string(),
            "capture.base-iface-routes | \
            routes.running.next-hop-interface:=\"b"
                .len()
                - 1
        )
    );
    assert!(cap_con.value_capture.is_none());
}

#[test]
fn test_policy_capture_with_equal() {
    let cap_con = NetworkCaptureCommand::parse(
        r#"
        capture.base-iface-routes | routes.running.next-hop-interface=="br1"
        "#
        .trim(),
    )
    .unwrap();

    assert_eq!(
        cap_con.key_capture.as_ref(),
        Some(&"base-iface-routes".to_string())
    );
    assert_eq!(cap_con.action, NetworkCaptureAction::Equal);
    assert_eq!(
        cap_con.key,
        NetworkCaptureToken::Path(
            vec![
                "routes".to_string(),
                "running".to_string(),
                "next-hop-interface".to_string(),
            ],
            "capture.base-iface-routes | r".len() - 1,
        )
    );
    assert_eq!(
        cap_con.value,
        NetworkCaptureToken::Value(
            "br1".to_string(),
            "capture.base-iface-routes | \
            routes.running.next-hop-interface==\"b"
                .len()
                - 1,
        ),
    );
    assert!(cap_con.value_capture.is_none());
}

#[test]
fn test_policy_capture_simple_store() {
    let cap_con = NetworkCaptureCommand::parse(
        r"
        just store it
        "
        .trim(),
    )
    .unwrap();

    assert!(cap_con.key_capture.is_none());
    assert_eq!(cap_con.action, NetworkCaptureAction::None);
    assert!(cap_con.key == NetworkCaptureToken::default());
    assert!(cap_con.value == NetworkCaptureToken::default());
    assert!(cap_con.value_capture.is_none());
}

#[test]
fn test_policy_capture_equal_to_prop_path() {
    let cap_con = NetworkCaptureCommand::parse(
        "routes.running.next-hop-interface == \
        capture.primary-nic.interfaces.0.name",
    )
    .unwrap();

    assert!(cap_con.key_capture.is_none());
    assert_eq!(cap_con.action, NetworkCaptureAction::Equal);
    assert_eq!(
        cap_con.key,
        NetworkCaptureToken::Path(
            vec![
                "routes".to_string(),
                "running".to_string(),
                "next-hop-interface".to_string(),
            ],
            0
        )
    );
    assert_eq!(
        cap_con.value,
        NetworkCaptureToken::Path(
            vec![
                "interfaces".to_string(),
                "0".to_string(),
                "name".to_string(),
            ],
            "routes.running.next-hop-interface == \
            capture.primary-nic.i"
                .len()
                - 1
        )
    );
    assert_eq!(cap_con.value_capture, Some("primary-nic".to_string()));
}

#[test]
fn test_policy_capture_retain_only() {
    let cap_con =
        NetworkCaptureCommand::parse(" dns-resolver.running").unwrap();

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

    let mut state = cap_con.execute(&current, &HashMap::new()).unwrap();
    let empty_state = NetworkState::new();

    assert!(cap_con.key_capture.is_none());
    assert_eq!(cap_con.action, NetworkCaptureAction::None);
    assert_eq!(
        cap_con.key,
        NetworkCaptureToken::Path(
            vec!["dns-resolver".to_string(), "running".to_string(),],
            0
        )
    );
    assert!(cap_con.value == NetworkCaptureToken::default());
    assert!(cap_con.value_capture.is_none());

    assert_eq!(state.dns, current.dns);

    state.dns = empty_state.dns.clone();
    state.prop_list = Vec::new();
    assert_eq!(state, empty_state);
}

#[test]
fn test_policy_capture_route_rule() {
    let cap_con =
        NetworkCaptureCommand::parse("route-rules.config.route-table==500")
            .unwrap();

    let current: NetworkState = serde_yaml::from_str(
        r"---
        routes:
          config:
          - destination: 192.168.2.0/24
            metric: 108
            next-hop-address: 192.168.1.3
            next-hop-interface: eth1
            table-id: 200
          - destination: 2001:db8:a::/64
            metric: 108
            next-hop-address: 2001:db8:1::2
            next-hop-interface: eth1
            table-id: 500
        route-rules:
          config:
            - ip-from: 192.168.3.2/32
              route-table: 200
            - ip-from: 2001:db8:b::/64
              route-table: 500
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            mtu: 1500
            ipv4:
              enabled: true
              dhcp: false
              address:
              - ip: 192.168.1.1
                prefix-length: 24
            ipv6:
              enabled: true
              dhcp: false
              autoconf: false
              address:
              - ip: 2001:db8:1::1
                prefix-length: 64
        ",
    )
    .unwrap();

    let state = cap_con.execute(&current, &HashMap::new()).unwrap();

    let rules = state.rules.config.as_ref().unwrap();
    assert_eq!(rules.len(), 1);
    assert_eq!(rules[0].ip_from, Some("2001:db8:b::/64".to_string()));
    assert_eq!(rules[0].table_id, Some(500));
}
