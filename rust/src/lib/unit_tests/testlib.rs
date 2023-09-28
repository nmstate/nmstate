// SPDX-License-Identifier: Apache-2.0

use crate::{
    BondConfig, BondInterface, BondMode, EthernetInterface, Interface,
    InterfaceType, Interfaces, LinuxBridgeConfig, LinuxBridgeInterface,
    LinuxBridgePortConfig, MergedInterfaces, OvsBridgeConfig,
    OvsBridgeInterface, OvsBridgePortConfig, OvsInterface, RouteEntry,
    RouteRuleEntry, RouteRules, Routes, UnknownInterface, VlanConfig,
    VlanInterface,
};

pub(crate) fn new_eth_iface(name: &str) -> Interface {
    let mut iface = EthernetInterface::new();
    iface.base.name = name.to_string();
    Interface::Ethernet(iface)
}

pub(crate) fn new_unknown_iface(name: &str) -> Interface {
    let mut iface = UnknownInterface::new();
    iface.base.name = name.to_string();
    Interface::Unknown(iface)
}

pub(crate) fn new_br_iface(name: &str) -> Interface {
    let mut iface = LinuxBridgeInterface::new();
    iface.base.name = name.to_string();
    Interface::LinuxBridge(iface)
}

fn new_bond_iface(name: &str) -> Interface {
    let mut iface = BondInterface::new();
    iface.base.name = name.to_string();
    Interface::Bond(iface)
}

pub(crate) fn new_ovs_br_iface(name: &str, port_names: &[&str]) -> Interface {
    let mut br0 = OvsBridgeInterface::new();
    br0.base.iface_type = InterfaceType::OvsBridge;
    br0.base.name = name.to_string();
    let mut br_conf = OvsBridgeConfig::new();
    let mut br_port_confs = Vec::new();
    for port_name in port_names {
        let mut br_port_conf = OvsBridgePortConfig::new();
        br_port_conf.name = port_name.to_string();
        br_port_confs.push(br_port_conf);
    }
    br_conf.ports = Some(br_port_confs);
    br0.bridge = Some(br_conf);
    Interface::OvsBridge(br0)
}

pub(crate) fn new_ovs_iface(name: &str, ctrl_name: &str) -> Interface {
    let mut iface = OvsInterface::new();
    iface.base.iface_type = InterfaceType::OvsInterface;
    iface.base.name = name.to_string();
    iface.base.controller = Some(ctrl_name.to_string());
    iface.base.controller_type = Some(InterfaceType::OvsBridge);
    Interface::OvsInterface(iface)
}

pub(crate) fn new_vlan_iface(name: &str, parent: &str, id: u16) -> Interface {
    let mut iface = VlanInterface::new();
    iface.base.name = name.to_string();
    iface.base.iface_type = InterfaceType::Vlan;
    iface.vlan = Some(VlanConfig {
        base_iface: parent.to_string(),
        id,
        ..Default::default()
    });
    Interface::Vlan(iface)
}

pub(crate) fn new_nested_4_ifaces() -> [Interface; 6] {
    let br0 = new_br_iface("br0");
    let mut br1 = new_br_iface("br1");
    let mut br2 = new_br_iface("br2");
    let mut br3 = new_br_iface("br3");
    let mut p1 = new_eth_iface("p1");
    let mut p2 = new_eth_iface("p2");

    br1.base_iface_mut().controller = Some("br0".to_string());
    br1.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
    br2.base_iface_mut().controller = Some("br1".to_string());
    br2.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
    br3.base_iface_mut().controller = Some("br2".to_string());
    br3.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
    p1.base_iface_mut().controller = Some("br3".to_string());
    p1.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
    p2.base_iface_mut().controller = Some("br3".to_string());
    p2.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);

    // Place the ifaces in mixed order to complex the work
    [br0, br1, br2, br3, p1, p2]
}

pub(crate) fn bridge_with_ports(name: &str, ports: &[&str]) -> Interface {
    let ports = ports
        .iter()
        .map(|port| LinuxBridgePortConfig {
            name: port.to_string(),
            ..Default::default()
        })
        .collect::<Vec<_>>();

    let mut br0 = new_br_iface(name);
    if let Interface::LinuxBridge(br) = &mut br0 {
        br.bridge = Some(LinuxBridgeConfig {
            port: Some(ports),
            ..Default::default()
        })
    };
    br0
}

pub(crate) fn bond_with_ports(name: &str, ports: &[&str]) -> Interface {
    let ports = ports.iter().map(|p| p.to_string()).collect::<Vec<String>>();
    let mut iface = new_bond_iface(name);
    if let Interface::Bond(bond_iface) = &mut iface {
        bond_iface.bond = Some(BondConfig {
            mode: Some(BondMode::RoundRobin),
            port: Some(ports),
            ..Default::default()
        });
    }
    iface
}

pub(crate) const TEST_NIC: &str = "eth1";
pub(crate) const TEST_IPV4_NET1: &str = "192.0.2.0/24";
pub(crate) const TEST_IPV4_ADDR1: &str = "198.51.100.1";
pub(crate) const TEST_IPV6_NET1: &str = "2001:db8:1::/64";
pub(crate) const TEST_IPV6_ADDR1: &str = "2001:db8:1::1";
pub(crate) const TEST_IPV6_NET2: &str = "2001:db8:2::/64";
pub(crate) const TEST_IPV6_ADDR2: &str = "2001:db8:2::2";
pub(crate) const TEST_ROUTE_METRIC: i64 = 100;
pub(crate) const TEST_TABLE_ID1: u32 = 101;
pub(crate) const TEST_TABLE_ID2: u32 = 102;
pub(crate) const TEST_RULE_IPV6_FROM: &str = "2001:db8:1::2/128";
pub(crate) const TEST_RULE_IPV4_FROM: &str = "192.0.2.1/32";
pub(crate) const TEST_RULE_IPV6_TO: &str = "2001:db8:2::2/128";
pub(crate) const TEST_RULE_IPV4_TO: &str = "198.51.100.1/32";
pub(crate) const TEST_RULE_PRIORITY1: i64 = 201;
pub(crate) const TEST_RULE_PRIORITY2: i64 = 202;
pub(crate) const TEST_RULE_FWMARK1: u32 = 0x72;
pub(crate) const TEST_RULE_FWMASK1: u32 = 0;
pub(crate) const TEST_RULE_FWMARK2: u32 = 0x50;
pub(crate) const TEST_RULE_FWMASK2: u32 = 0x10;

pub(crate) fn gen_test_routes_conf() -> Routes {
    let mut ret = Routes::new();
    ret.running = Some(gen_test_route_entries());
    ret.config = Some(gen_test_route_entries());
    ret
}

pub(crate) fn gen_test_route_entries() -> Vec<RouteEntry> {
    vec![
        gen_route_entry(TEST_IPV6_NET1, TEST_NIC, TEST_IPV6_ADDR1),
        gen_route_entry(TEST_IPV4_NET1, TEST_NIC, TEST_IPV4_ADDR1),
    ]
}

pub(crate) fn gen_route_entry(
    dst: &str,
    next_hop_iface: &str,
    next_hop_addr: &str,
) -> RouteEntry {
    let mut ret = RouteEntry::new();
    ret.destination = Some(dst.to_string());
    ret.next_hop_iface = Some(next_hop_iface.to_string());
    ret.next_hop_addr = Some(next_hop_addr.to_string());
    ret.metric = Some(TEST_ROUTE_METRIC);
    ret
}

pub(crate) fn gen_test_rules_conf() -> RouteRules {
    RouteRules {
        config: Some(gen_test_rule_entries()),
    }
}

pub(crate) fn gen_test_rule_entries() -> Vec<RouteRuleEntry> {
    vec![
        gen_rule_entry(
            TEST_RULE_IPV6_FROM,
            TEST_RULE_IPV6_TO,
            TEST_RULE_PRIORITY1,
            TEST_TABLE_ID1,
            TEST_RULE_FWMARK1,
            TEST_RULE_FWMASK1,
        ),
        gen_rule_entry(
            TEST_RULE_IPV4_FROM,
            TEST_RULE_IPV4_TO,
            TEST_RULE_PRIORITY2,
            TEST_TABLE_ID2,
            TEST_RULE_FWMARK2,
            TEST_RULE_FWMASK2,
        ),
    ]
}

fn gen_rule_entry(
    ip_from: &str,
    ip_to: &str,
    priority: i64,
    table_id: u32,
    fwmark: u32,
    fwmask: u32,
) -> RouteRuleEntry {
    RouteRuleEntry {
        family: None,
        state: None,
        ip_from: Some(ip_from.to_string()),
        ip_to: Some(ip_to.to_string()),
        table_id: Some(table_id),
        priority: Some(priority),
        fwmark: Some(fwmark),
        fwmask: Some(fwmask),
        ..Default::default()
    }
}

pub(crate) fn new_test_nic_with_static_ip() -> Interface {
    serde_yaml::from_str(
        r"
        name: eth1
        type: ethernet
        state: up
        mtu: 1500
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
        ",
    )
    .unwrap()
}

fn new_test_nic2_with_static_ip() -> Interface {
    serde_yaml::from_str(
        r"
        name: eth2
        type: ethernet
        state: up
        mtu: 1500
        ipv4:
          address:
          - ip: 192.0.2.253
            prefix-length: 24
          - ip: 192.0.2.254
            prefix-length: 24
          dhcp: false
          enabled: true
        ipv6:
          address:
            - ip: 2001:db8:3::1
              prefix-length: 64
            - ip: 2001:db8:4::1
              prefix-length: 64
          autoconf: false
          dhcp: false
          enabled: true
        ",
    )
    .unwrap()
}

pub(crate) fn gen_merged_ifaces_for_route_test() -> MergedInterfaces {
    let mut ifaces = Interfaces::new();
    ifaces.push(new_test_nic_with_static_ip());
    ifaces.push(new_test_nic2_with_static_ip());
    let mut current = Interfaces::new();
    current.push(new_eth_iface("eth1"));
    current.push(new_eth_iface("eth2"));
    MergedInterfaces::new(ifaces, current, false, false).unwrap()
}
