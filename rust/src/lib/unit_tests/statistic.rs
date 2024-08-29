// SPDX-License-Identifier: Apache-2.0

use crate::{
    BaseInterface, DummyInterface, Interface, InterfaceType, NetworkState,
    NmstateFeature,
};

const CUR_STATE_STR: &str = r"---
    interfaces:
    - name: eth1
      type: ethernet
      state: up
      mac-address: 01:23:45:67:89:AB
    - name: eth2
      type: ethernet
      state: up
      mac-address: 01:23:45:67:89:AC";

#[test]
fn test_statistic_topology_static_ip() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
        - name: br0.101
          type: vlan
          vlan:
            base-iface: br0
            id: 101
          ipv4:
            address:
            - ip: 192.0.2.252
              prefix-length: 24
            - ip: 192.0.2.251
              prefix-length: 24
            dhcp: false
            enabled: true
          ipv6:
            address:
              - ip: 2001:db8:2::1
                prefix-length: 64
              - ip: 2001:db8:1::1
                prefix-length: 64
            autoconf: false
            dhcp: false
            enabled: true
        - name: bond1
          type: bond
          link-aggregation:
            mode: 1
            ports:
              - eth1
              - eth2
        - name: br0
          type: linux-bridge
          state: up
          bridge:
            port:
            - name: bond1",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(
        stat.topology.as_slice(),
        ["static_ip4,static_ip6 -> vlan -> linux-bridge -> bond -> ethernet"]
    )
}

#[test]
fn test_statistic_feature_dns() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        dns-resolver:
          config:
            options:
            - rotate
            - debug
            - ndots:8
            search:
            - example.com
            - example.org
            server:
            - 2001:db8:1::1
            - 2001:db8:1::2
            - 192.0.2.251",
    )
    .unwrap();
    let current = NetworkState::default();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(
        stat.features.as_slice(),
        [
            NmstateFeature::StaticDnsNameServer,
            NmstateFeature::StaticDnsOption,
            NmstateFeature::StaticDnsSearch,
        ],
    )
}

#[test]
fn test_statistic_feature_route() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
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
        routes:
          config:
          - destination: 0.0.0.0/0
            next-hop-address: 192.0.2.1
            next-hop-interface: eth1
            metric: 103
        ",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(stat.features.as_slice(), [NmstateFeature::StaticRoute])
}

#[test]
fn test_statistic_feature_route_rule() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        route-rules:
          config:
            - ip-from: 192.168.3.2/32
              suppress-prefix-length: 0
              route-table: 200
            - ip-from: 2001:db8:b::/64
              suppress-prefix-length: 1
              route-table: 200
        ",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(
        stat.features.as_slice(),
        [
            NmstateFeature::StaticRouteRule,
            NmstateFeature::StaticRouteRuleSuppressPrefixLength
        ]
    )
}

#[test]
fn test_statistic_feature_hostname() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        hostname:
          config: hosta.example.org",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(stat.features.as_slice(), [NmstateFeature::StaticHostname])
}

#[test]
fn test_statistic_feature_sriov() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            ethernet:
              sr-iov:
                total-vfs: 2
          - name: sriov:eth1:1
            type: ethernet
            state: up",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(
        stat.features.as_slice(),
        [
            NmstateFeature::IfaceNameReferedBySriovVfId,
            NmstateFeature::Sriov,
        ]
    )
}

#[test]
fn test_statistic_feature_ovs_dpdk_with_bond() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        interfaces:
        - name: ovs0
          type: ovs-interface
          state: up
          mtu: 9000
          dpdk:
            devargs: "0000:ab:cd.0"
            rx-queue: 100
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            options:
              datapath: "netdev"
            port:
            - name: ovs0
            - name: bond99
              link-aggregation:
                mode: balance-slb
                ports:
                  - name: eth2
                  - name: eth1
        ovs-db:
          other_config:
            dpdk-init: "true"
        "#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(
        stat.features.as_slice(),
        [
            NmstateFeature::OvsBond,
            NmstateFeature::OvsDbGlobal,
            NmstateFeature::OvsDpdk,
        ]
    )
}

#[test]
fn test_statistic_feature_ovs_patch_with_iface_ovsdb() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        interfaces:
        - name: patch0
          type: ovs-interface
          state: up
          ovs-db:
            external_ids:
              gris: abc
          patch:
            peer: patch1
        - name: ovs-br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: patch0
        - name: patch1
          type: ovs-interface
          state: up
          patch:
            peer: patch0
        - name: ovs-br1
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: patch1
        "#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(
        stat.features.as_slice(),
        [NmstateFeature::OvsDbInterface, NmstateFeature::OvsPatch,]
    )
}

#[test]
fn test_statistic_feature_ovn_map() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        ovn:
          bridge-mappings:
            - localnet: blue
              bridge: ovsbr1
            - localnet: red
              bridge: ovsbr2
        "#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(stat.features.as_slice(), [NmstateFeature::OvnMapping])
}

#[test]
fn test_statistic_feature_mac_based_iface_id() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        interfaces:
          - name: wan0
            type: ethernet
            state: up
            identifier: mac-address
            mac-address: 01:23:45:67:89:AB
        "#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(
        stat.features.as_slice(),
        [NmstateFeature::MacBasedIdentifier]
    )
}

#[test]
fn test_statistic_feature_dhcp_hostname() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            ipv4:
              dhcp: true
              dhcp-client-id: iaid+duid
              enabled: true
              dhcp-send-hostname: true
              dhcp-custom-hostname: c9.example.org
            ipv6:
              dhcp: true
              autoconf: true
              enabled: true
              dhcp-send-hostname: true
              dhcp-custom-hostname: c9.example.net
        "#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(
        stat.features.as_slice(),
        [
            NmstateFeature::Dhcpv4CustomHostname,
            NmstateFeature::Dhcpv6CustomHostname,
        ]
    )
}

#[test]
fn test_statistic_feature_lldp() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            lldp:
              enabled: true
        "#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let stat = desired.statistic(&current).unwrap();

    assert_eq!(stat.features.as_slice(), [NmstateFeature::Lldp,])
}

#[test]
fn test_statistic_feature_iface_count() {
    for (count, feature) in [
        (11, NmstateFeature::IfaceCount10Plus),
        (51, NmstateFeature::IfaceCount50Plus),
        (101, NmstateFeature::IfaceCount100Plus),
        (499, NmstateFeature::IfaceCount200Plus),
        (500, NmstateFeature::IfaceCount500Plus),
    ] {
        let desired: NetworkState = gen_dummy_ifaces(count);
        let current: NetworkState =
            serde_yaml::from_str(CUR_STATE_STR).unwrap();

        let stat = desired.statistic(&current).unwrap();

        assert_eq!(stat.features.as_slice(), [feature])
    }
}

fn gen_dummy_ifaces(iface_count: usize) -> NetworkState {
    let mut ret = NetworkState::default();

    for i in 0..iface_count {
        ret.interfaces
            .push(Interface::Dummy(Box::new(DummyInterface {
                base: BaseInterface {
                    name: format!("dummy{i}"),
                    iface_type: InterfaceType::Dummy,
                    ..Default::default()
                },
            })));
    }
    ret
}

#[test]
fn test_statistic_multple_states() {
    let mut desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: br0.101
            type: vlan
            vlan:
              base-iface: br0
              id: 101
            ipv4:
              address:
              - ip: 192.0.2.252
                prefix-length: 24
              - ip: 192.0.2.251
                prefix-length: 24
              dhcp: false
              enabled: true
            ipv6:
              address:
                - ip: 2001:db8:2::1
                  prefix-length: 64
                - ip: 2001:db8:1::1
                  prefix-length: 64
              autoconf: false
              dhcp: false
              enabled: true
          - name: bond1
            type: bond
            link-aggregation:
              mode: 1
              ports:
                - eth1
                - eth2
          - name: br0
            type: linux-bridge
            state: up
            bridge:
              port:
              - name: bond1
            ipv4:
              address:
              - ip: 192.0.2.252
                prefix-length: 24
              - ip: 192.0.2.251
                prefix-length: 24
              dhcp: false
              enabled: true
            ipv6:
              address:
                - ip: 2001:db8:2::1
                  prefix-length: 64
                - ip: 2001:db8:1::1
                  prefix-length: 64
              autoconf: false
              dhcp: false
              enabled: true
          - name: eth2
            type: ethernet
            ethernet:
              sr-iov:
                total-vfs: 2",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(CUR_STATE_STR).unwrap();

    let desired2: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
        - name: br0
          type: linux-bridge
          state: absent",
    )
    .unwrap();

    desired.merge_desire(&desired2);
    let stat = desired.statistic(&current).unwrap();

    assert_eq!(stat.topology.as_slice(), ["bond -> ethernet"]);
    assert_eq!(stat.features.as_slice(), [NmstateFeature::Sriov]);
}
