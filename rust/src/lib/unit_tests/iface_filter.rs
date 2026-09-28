// SPDX-License-Identifier: Apache-2.0

use crate::{
    Interface, InterfaceType, Interfaces, NetworkState, UnknownInterface,
    query_apply::iface_filter::get_related_iface_names,
};

fn related(yaml: &str, name: &str) -> Option<Vec<String>> {
    let state = NetworkState::new_from_yaml(yaml).unwrap();
    get_related_iface_names(&state.interfaces, name).map(|mut v| {
        v.sort();
        v
    })
}

fn names(names: &[&str]) -> Option<Vec<String>> {
    Some(names.iter().map(|n| n.to_string()).collect())
}

fn bridge_with_ports(port_count: usize) -> String {
    let mut yaml = String::from(
        "interfaces:\n- name: br0\n  type: linux-bridge\n  bridge:\n    \
         port:\n",
    );
    for i in 0..port_count {
        yaml.push_str(&format!("    - name: eth{i}\n"));
    }
    for i in 0..port_count {
        yaml.push_str(&format!(
            "- name: eth{i}\n  type: ethernet\n  controller: br0\n"
        ));
    }
    yaml
}

const TOPOLOGY: &str = r#"
interfaces:
- name: eth1
  type: ethernet
  controller: bond0
- name: eth2
  type: ethernet
  controller: bond0
- name: bond0
  type: bond
  link-aggregation:
    mode: active-backup
    port: [eth1, eth2]
- name: bond0.10
  type: vlan
  controller: br0
  vlan:
    base-iface: bond0
    id: 10
- name: br0
  type: linux-bridge
  bridge:
    port:
    - name: bond0.10
- name: veth0
  type: veth
  veth:
    peer: veth1
- name: veth1
  type: veth
  veth:
    peer: veth0
- name: ipvl0
  type: ipvlan
  ipvlan:
    base-iface: eth1
- name: vrf0
  type: vrf
  vrf:
    port: [eth3]
    route-table-id: 100
- name: eth3
  type: ethernet
  controller: vrf0
- name: lo
  type: loopback
"#;

#[test]
fn test_related_loopback() {
    assert_eq!(related(TOPOLOGY, "lo"), names(&["lo"]));
}

#[test]
fn test_related_bond_includes_ports() {
    assert_eq!(
        related(TOPOLOGY, "bond0"),
        names(&["bond0", "eth1", "eth2"])
    );
}

#[test]
fn test_related_port_includes_controller() {
    assert_eq!(related(TOPOLOGY, "eth1"), names(&["bond0", "eth1"]));
}

#[test]
fn test_related_vlan_includes_parent_and_controller() {
    assert_eq!(
        related(TOPOLOGY, "bond0.10"),
        names(&["bond0", "bond0.10", "br0"])
    );
}

#[test]
fn test_related_bridge_port_listed_once() {
    // bond0.10 is both a listed bridge port and has br0 as controller.
    assert_eq!(related(TOPOLOGY, "br0"), names(&["bond0.10", "br0"]));
}

#[test]
fn test_related_veth_includes_peer() {
    assert_eq!(related(TOPOLOGY, "veth0"), names(&["veth0", "veth1"]));
}

#[test]
fn test_related_ipvlan_includes_base() {
    assert_eq!(related(TOPOLOGY, "ipvl0"), names(&["eth1", "ipvl0"]));
}

#[test]
fn test_related_vrf_includes_ports() {
    assert_eq!(related(TOPOLOGY, "vrf0"), names(&["eth3", "vrf0"]));
}

#[test]
fn test_related_hsr_includes_ports() {
    let yaml = r#"
interfaces:
- name: hsr0
  type: hsr
  hsr:
    port1: eth1
    port2: eth2
    protocol: prp
    multicast-spec: 0
- name: eth1
  type: ethernet
- name: eth2
  type: ethernet
"#;
    assert_eq!(related(yaml, "hsr0"), names(&["eth1", "eth2", "hsr0"]));
}

#[test]
fn test_related_unknown_iface_falls_back() {
    assert_eq!(related(TOPOLOGY, "nonexistent"), None);
}

#[test]
fn test_related_missing_parent_falls_back() {
    let yaml = r#"
interfaces:
- name: eth1.10
  type: vlan
  vlan:
    base-iface: eth1
    id: 10
"#;
    assert_eq!(related(yaml, "eth1.10"), None);
}

#[test]
fn test_related_ovs_falls_back() {
    let yaml = r#"
interfaces:
- name: br-ex
  type: ovs-interface
- name: br-ex
  type: ovs-bridge
  bridge:
    port:
    - name: br-ex
"#;
    assert_eq!(related(yaml, "br-ex"), None);
}

#[test]
fn test_related_ovs_system_port_falls_back() {
    let yaml = r#"
interfaces:
- name: eth1
  type: ethernet
  controller: ovs-system
"#;
    assert_eq!(related(yaml, "eth1"), None);
}

#[test]
fn test_related_tun_falls_back() {
    // Kernel TUN interfaces are reported by nispor as InterfaceType::Tun.
    let mut iface = UnknownInterface::new();
    iface.base.name = "tap0".to_string();
    iface.base.iface_type = InterfaceType::Tun;
    let mut ifaces = Interfaces::new();
    ifaces.push(Interface::Unknown(Box::new(iface)));
    assert_eq!(get_related_iface_names(&ifaces, "tap0"), None);
}

#[test]
fn test_related_limit_is_16_besides_iface() {
    assert_eq!(
        related(&bridge_with_ports(16), "br0").map(|v| v.len()),
        Some(17)
    );
    assert_eq!(related(&bridge_with_ports(17), "br0"), None);
    assert!(related(&bridge_with_ports(17), "eth0").is_some());
}
