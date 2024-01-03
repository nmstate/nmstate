// SPDX-License-Identifier: Apache-2.0

use crate::{
    nm::route_rule::store_route_rule_config,
    unit_tests::testlib::{
        gen_test_routes_conf, gen_test_rules_conf, new_eth_iface,
        new_test_nic_with_static_ip, TEST_NIC, TEST_RULE_IPV4_FROM,
        TEST_RULE_IPV4_TO, TEST_RULE_IPV6_FROM, TEST_RULE_IPV6_TO,
        TEST_RULE_PRIORITY1, TEST_RULE_PRIORITY2, TEST_TABLE_ID1,
        TEST_TABLE_ID2,
    },
    InterfaceType, Interfaces, MergedNetworkState, NetworkState,
    RouteRuleEntry,
};

#[test]
fn test_add_rules_to_new_interface() {
    let mut cur_net_state = NetworkState::new();
    cur_net_state.interfaces.push(new_eth_iface(TEST_NIC));

    let des_iface = new_test_nic_with_static_ip();
    let mut des_ifaces = Interfaces::new();
    des_ifaces.push(des_iface);
    let mut des_net_state = NetworkState::new();
    des_net_state.interfaces = des_ifaces;
    des_net_state.routes = gen_test_routes_conf();
    des_net_state.rules = gen_test_rules_conf();

    let mut merged_state =
        MergedNetworkState::new(des_net_state, cur_net_state, false).unwrap();
    store_route_rule_config(&mut merged_state).unwrap();

    let iface = merged_state
        .interfaces
        .get_iface(TEST_NIC, InterfaceType::Unknown)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    let ipv6_config_rules = iface
        .base_iface()
        .ipv6
        .as_ref()
        .unwrap()
        .rules
        .as_ref()
        .unwrap();

    assert_eq!(ipv6_config_rules.len(), 1);

    assert_eq!(
        ipv6_config_rules[0].ip_from.as_ref().unwrap().as_str(),
        TEST_RULE_IPV6_FROM,
    );
    assert_eq!(
        ipv6_config_rules[0].ip_to.as_ref().unwrap().as_str(),
        TEST_RULE_IPV6_TO,
    );
    assert_eq!(ipv6_config_rules[0].priority.unwrap(), TEST_RULE_PRIORITY1);
    assert_eq!(ipv6_config_rules[0].table_id.unwrap(), TEST_TABLE_ID1);

    let ipv4_config_rules = iface
        .base_iface()
        .ipv4
        .as_ref()
        .unwrap()
        .rules
        .as_ref()
        .unwrap();

    assert_eq!(ipv4_config_rules.len(), 1);

    assert_eq!(
        ipv4_config_rules[0].ip_from.as_ref().unwrap().as_str(),
        TEST_RULE_IPV4_FROM,
    );
    assert_eq!(
        ipv4_config_rules[0].ip_to.as_ref().unwrap().as_str(),
        TEST_RULE_IPV4_TO,
    );
    assert_eq!(ipv4_config_rules[0].priority.unwrap(), TEST_RULE_PRIORITY2);
    assert_eq!(ipv4_config_rules[0].table_id.unwrap(), TEST_TABLE_ID2);
}

#[test]
fn test_route_rule_ignore_absent_ifaces() {
    let desired: NetworkState = serde_yaml::from_str(
        r"
interfaces:
- name: br0
  state: absent
  type: linux-bridge
route-rules:
  config:
  - route-table: 200
    state: absent
",
    )
    .unwrap();

    let current: NetworkState = serde_yaml::from_str(
        r"
interfaces:
- name: eth1
  type: ethernet
  state: up
- name: br0
  type: linux-bridge
  state: up
  ipv4:
    address:
    - ip: 192.0.2.251
      prefix-length: 24
    dhcp: false
    enabled: true
  bridge:
    options:
      stp:
        enabled: false
    port:
    - name: eth1
routes:
  config:
    - destination: 198.51.100.0/24
      metric: 150
      next-hop-address: 192.0.2.1
      next-hop-interface: br0
      table-id: 200
route-rules:
  config:
    - ip-from: 192.51.100.2/32
      route-table: 200
",
    )
    .unwrap();

    let mut merged_state =
        MergedNetworkState::new(desired, current, false).unwrap();

    store_route_rule_config(&mut merged_state).unwrap();

    let eth1_iface = merged_state
        .interfaces
        .get_iface("eth1", InterfaceType::Ethernet)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    let br0_iface = merged_state
        .interfaces
        .get_iface("br0", InterfaceType::LinuxBridge)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert!(eth1_iface.is_up());
    assert!(br0_iface.is_absent());
}

#[test]
fn test_route_rule_use_auto_route_table_id() {
    let current: NetworkState = serde_yaml::from_str(
        r"
---
interfaces:
  - name: br0
    type: ovs-interface
    state: up
    ipv4:
      enabled: true
      dhcp: true
      auto-dns: false
      auto-routes: true
      auto-gateway: true
      auto-route-table-id: 500
    ipv6:
      enabled: false
  - name: br0
    type: ovs-bridge
    state: up
    bridge:
      port:
        - name: br0
",
    )
    .unwrap();

    let desired: NetworkState = serde_yaml::from_str(
        r"
---
route-rules:
  config:
    - route-table: 500
      priority: 3200
      ip-to: 192.0.3.0/24
    - route-table: 500
      priority: 3200
      ip-from: 192.0.3.0/24
",
    )
    .unwrap();

    let expected_rules: Vec<RouteRuleEntry> = serde_yaml::from_str(
        r"
- route-table: 500
  priority: 3200
  ip-to: 192.0.3.0/24
- route-table: 500
  priority: 3200
  ip-from: 192.0.3.0/24
",
    )
    .unwrap();

    let mut merged_state =
        MergedNetworkState::new(desired, current, false).unwrap();

    store_route_rule_config(&mut merged_state).unwrap();

    let ovs_iface = merged_state
        .interfaces
        .get_iface("br0", InterfaceType::OvsInterface)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(ovs_iface.iface_type(), InterfaceType::OvsInterface);
    assert_eq!(
        ovs_iface.base_iface().ipv4.as_ref().unwrap().rules,
        Some(expected_rules)
    );
}

#[test]
fn test_route_rule_use_default_auto_route_table_id() {
    let current: NetworkState = serde_yaml::from_str(
        r"
---
interfaces:
  - name: eth1
    type: ethernet
    state: up
    ipv4:
      enabled: true
      dhcp: true
      auto-dns: true
      auto-routes: true
      auto-gateway: true
    ipv6:
      enabled: false
",
    )
    .unwrap();

    let desired: NetworkState = serde_yaml::from_str(
        r"
---
route-rules:
  config:
    - priority: 3200
      ip-to: 192.0.3.0/24
    - priority: 3200
      ip-from: 192.0.3.0/24
",
    )
    .unwrap();

    let expected_rules: Vec<RouteRuleEntry> = serde_yaml::from_str(
        r"
- route-table: 254
  priority: 3200
  ip-to: 192.0.3.0/24
- route-table: 254
  priority: 3200
  ip-from: 192.0.3.0/24
",
    )
    .unwrap();

    let mut merged_state =
        MergedNetworkState::new(desired, current, false).unwrap();

    store_route_rule_config(&mut merged_state).unwrap();

    let iface = merged_state
        .interfaces
        .get_iface("eth1", InterfaceType::Ethernet)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(
        iface.base_iface().ipv4.as_ref().unwrap().rules,
        Some(expected_rules)
    );
}

#[test]
fn test_route_rule_use_loopback() {
    let current: NetworkState = serde_yaml::from_str(
        r"
---
interfaces:
  - name: lo
    type: loopback
    state: up
    mtu: 65536
    ipv4:
      enabled: true
      address:
      - ip: 127.0.0.1
        prefix-length: 8
    ipv6:
      enabled: true
      address:
      - ip: ::1
        prefix-length: 128
",
    )
    .unwrap();

    let desired: NetworkState = serde_yaml::from_str(
        r"---
        route-rules:
          config:
            - priority: 3200
              route-table: 255
              family: ipv4
            - priority: 3200
              route-table: 255
              family: ipv6",
    )
    .unwrap();

    let expected_ipv4_rules: Vec<RouteRuleEntry> = serde_yaml::from_str(
        r"
        - priority: 3200
          route-table: 255
          family: ipv4",
    )
    .unwrap();

    let expected_ipv6_rules: Vec<RouteRuleEntry> = serde_yaml::from_str(
        r"
        - priority: 3200
          route-table: 255
          family: ipv6",
    )
    .unwrap();

    let mut merged_state =
        MergedNetworkState::new(desired, current, false).unwrap();

    store_route_rule_config(&mut merged_state).unwrap();

    let iface = merged_state
        .interfaces
        .get_iface("lo", InterfaceType::Loopback)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(
        iface.base_iface().ipv4.as_ref().unwrap().rules,
        Some(expected_ipv4_rules)
    );
    assert_eq!(
        iface.base_iface().ipv6.as_ref().unwrap().rules,
        Some(expected_ipv6_rules)
    );
}
