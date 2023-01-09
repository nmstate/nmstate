// SPDX-License-Identifier: Apache-2.0

use crate::{
    nm::route::store_route_config,
    unit_tests::testlib::{
        gen_test_routes_conf, new_eth_iface, new_test_nic_with_static_ip,
        TEST_IPV4_ADDR1, TEST_IPV4_NET1, TEST_IPV6_ADDR1, TEST_IPV6_NET1,
        TEST_NIC,
    },
    InterfaceType, Interfaces, MergedNetworkState, NetworkState, RouteEntry,
    RouteState,
};

#[test]
fn test_add_routes_to_new_interface() {
    let mut cur_net_state = NetworkState::new();
    cur_net_state.interfaces.push(new_eth_iface(TEST_NIC));

    let des_iface = new_test_nic_with_static_ip();
    let mut des_ifaces = Interfaces::new();
    des_ifaces.push(des_iface);
    let mut des_net_state = NetworkState::new();
    des_net_state.interfaces = des_ifaces;
    des_net_state.routes = gen_test_routes_conf();

    let mut merged_state =
        MergedNetworkState::new(des_net_state, cur_net_state, false, false)
            .unwrap();

    store_route_config(&mut merged_state).unwrap();

    let iface = merged_state
        .interfaces
        .get_iface(TEST_NIC, InterfaceType::Unknown)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    let config_routes = iface.base_iface().routes.as_ref().unwrap();

    assert_eq!(config_routes.len(), 2);
    assert_eq!(
        config_routes[0].destination.as_ref().unwrap().as_str(),
        TEST_IPV6_NET1
    );
    assert_eq!(
        config_routes[0].next_hop_iface.as_ref().unwrap().as_str(),
        TEST_NIC
    );
    assert_eq!(
        config_routes[0].next_hop_addr.as_ref().unwrap().as_str(),
        TEST_IPV6_ADDR1
    );
    assert_eq!(
        config_routes[1].destination.as_ref().unwrap().as_str(),
        TEST_IPV4_NET1
    );
    assert_eq!(
        config_routes[1].next_hop_iface.as_ref().unwrap().as_str(),
        TEST_NIC
    );
    assert_eq!(
        config_routes[1].next_hop_addr.as_ref().unwrap().as_str(),
        TEST_IPV4_ADDR1
    );
}

#[test]
fn test_wildcard_absent_routes() {
    let cur_iface = new_test_nic_with_static_ip();
    let mut cur_ifaces = Interfaces::new();
    cur_ifaces.push(cur_iface);
    let mut cur_net_state = NetworkState::new();
    cur_net_state.interfaces = cur_ifaces;
    cur_net_state.routes = gen_test_routes_conf();

    let mut des_net_state = NetworkState::new();
    let mut absent_routes = Vec::new();
    let mut absent_route = RouteEntry::new();
    absent_route.state = Some(RouteState::Absent);
    absent_route.next_hop_addr = Some(TEST_IPV4_ADDR1.to_string());
    absent_routes.push(absent_route);
    let mut absent_route = RouteEntry::new();
    absent_route.state = Some(RouteState::Absent);
    absent_route.next_hop_addr = Some(TEST_IPV6_ADDR1.to_string());
    absent_routes.push(absent_route);

    des_net_state.routes.config = Some(absent_routes);

    let mut merged_state =
        MergedNetworkState::new(des_net_state, cur_net_state, false, false)
            .unwrap();

    store_route_config(&mut merged_state).unwrap();

    let iface = merged_state
        .interfaces
        .get_iface(TEST_NIC, InterfaceType::Unknown)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(iface.base_iface().routes, Some(Vec::new()));
    assert_eq!(iface.name(), TEST_NIC);
    assert_eq!(iface.iface_type(), InterfaceType::Ethernet);
}

#[test]
fn test_absent_routes_with_iface_only() {
    let cur_iface = new_test_nic_with_static_ip();
    let mut cur_ifaces = Interfaces::new();
    cur_ifaces.push(cur_iface);
    let mut cur_net_state = NetworkState::new();
    cur_net_state.interfaces = cur_ifaces;
    cur_net_state.routes = gen_test_routes_conf();

    let mut des_net_state = NetworkState::new();
    let mut absent_routes = Vec::new();
    let mut absent_route = RouteEntry::new();
    absent_route.state = Some(RouteState::Absent);
    absent_route.next_hop_iface = Some(TEST_NIC.to_string());
    absent_routes.push(absent_route);
    des_net_state.routes.config = Some(absent_routes);

    let mut merged_state =
        MergedNetworkState::new(des_net_state, cur_net_state, false, false)
            .unwrap();

    store_route_config(&mut merged_state).unwrap();

    let iface = merged_state
        .interfaces
        .get_iface(TEST_NIC, InterfaceType::Unknown)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(iface.base_iface().routes, Some(Vec::new()));
    assert_eq!(iface.name(), TEST_NIC);
    assert_eq!(iface.iface_type(), InterfaceType::Ethernet);
}

#[test]
fn test_route_ignore_absent_ifaces() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"
interfaces:
- name: br0
  state: absent
  type: linux-bridge
routes:
  config:
  - next-hop-interface: br0
    state: absent
"#,
    )
    .unwrap();

    let current: NetworkState = serde_yaml::from_str(
        r#"
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
      table-id: 254
"#,
    )
    .unwrap();

    let mut merged_state =
        MergedNetworkState::new(desired, current, false, false).unwrap();
    store_route_config(&mut merged_state).unwrap();

    let br0_iface = merged_state
        .interfaces
        .get_iface("br0", InterfaceType::LinuxBridge)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    let eth1_iface = merged_state
        .interfaces
        .get_iface("eth1", InterfaceType::Ethernet)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    assert!(eth1_iface.is_up());
    assert!(br0_iface.is_absent());
}
