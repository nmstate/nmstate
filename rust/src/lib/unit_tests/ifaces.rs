// SPDX-License-Identifier: Apache-2.0

use crate::{
    unit_tests::testlib::{
        get_mac, new_eth_iface, new_ovs_br_iface, new_ovs_iface,
        new_unknown_iface, new_vlan_iface,
    },
    BondMode, ErrorKind, Interface, InterfaceState, InterfaceType, Interfaces,
    MergedInterfaces,
};

#[test]
fn test_resolve_unknown_type_absent_eth() {
    let mut cur_ifaces = Interfaces::new();
    cur_ifaces.push(new_eth_iface("eth2"));
    cur_ifaces.push(new_eth_iface("eth1"));

    let mut absent_iface = new_unknown_iface("eth1");
    absent_iface.base_iface_mut().state = InterfaceState::Absent;
    let mut ifaces = Interfaces::new();
    ifaces.push(absent_iface);

    let merged_ifaces =
        MergedInterfaces::new(ifaces, cur_ifaces, Default::default(), false)
            .unwrap();

    let iface = merged_ifaces
        .get_iface("eth1", InterfaceType::Ethernet)
        .unwrap();
    let apply_iface = iface.for_apply.as_ref().unwrap();

    assert_eq!(apply_iface.iface_type(), InterfaceType::Ethernet);
    assert!(apply_iface.is_absent());
}

#[test]
fn test_resolve_unknown_type_absent_multiple() {
    let mut cur_ifaces = Interfaces::new();
    cur_ifaces.push(new_ovs_br_iface("br0", &["br0", "p1", "p2"]));
    cur_ifaces.push(new_ovs_iface("br0", "br0"));
    cur_ifaces.push(new_ovs_iface("p1", "br0"));
    cur_ifaces.push(new_ovs_iface("p2", "br0"));

    let mut absent_iface = new_unknown_iface("br0");
    absent_iface.base_iface_mut().state = InterfaceState::Absent;
    let mut ifaces = Interfaces::new();
    ifaces.push(absent_iface);

    let merged_ifaces =
        MergedInterfaces::new(ifaces, cur_ifaces, Default::default(), false)
            .unwrap();

    let iface = merged_ifaces
        .get_iface("br0", InterfaceType::OvsBridge)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert!(iface.is_absent());

    let iface = merged_ifaces
        .get_iface("br0", InterfaceType::OvsInterface)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert!(iface.is_absent());
}

#[test]
fn test_vlan_over_ethernet_can_exist_after_ethernet_absent() {
    let mut current = Interfaces::new();
    current.push(new_eth_iface("eth0"));
    current.push(new_vlan_iface("eth0.10", "eth0", 10));

    let mut desired = Interfaces::new();
    let mut eth0 = new_eth_iface("eth0");
    eth0.base_iface_mut().state = InterfaceState::Absent;
    desired.push(eth0);

    let merged_ifaces =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    let iface = merged_ifaces
        .get_iface("eth0", InterfaceType::Ethernet)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    assert!(iface.is_absent());
    assert!(merged_ifaces
        .get_iface("eth0.10", InterfaceType::Vlan)
        .unwrap()
        .for_apply
        .is_none());
}

#[test]
fn test_check_orphan_vlan_change_parent() {
    let mut current = Interfaces::new();
    current.push(new_eth_iface("eth0"));
    current.push(new_vlan_iface("eth0.10", "eth0", 10));
    current.push(new_eth_iface("eth1"));

    let mut desired = Interfaces::new();
    let mut eth0 = new_eth_iface("eth0");
    eth0.base_iface_mut().state = InterfaceState::Absent;
    desired.push(eth0);
    desired.push(new_vlan_iface("eth0.10", "eth1", 10));
    desired.push(new_eth_iface("eth1"));

    let merged_ifaces =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();
    let iface = merged_ifaces
        .get_iface("eth0", InterfaceType::Ethernet)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    assert!(iface.is_absent());
    let iface = merged_ifaces
        .get_iface("eth0.10", InterfaceType::Vlan)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    assert!(iface.is_up());
    let iface = merged_ifaces
        .get_iface("eth1", InterfaceType::Ethernet)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    assert!(iface.is_up());
}

#[test]
fn test_ifaces_deny_unknonw_attribute() {
    let result = serde_yaml::from_str::<Interfaces>(
        r"---
- name: eth1
  type: ethernet
  state: up
  foo: bar
",
    );
    assert!(result.is_err());
    if let Err(e) = result {
        assert!(e.to_string().contains("unknown field"));
        assert!(e.to_string().contains("foo"));
    }
}

#[test]
fn test_ifaces_resolve_unknown_bond_iface() {
    let current = serde_yaml::from_str::<Interfaces>(
        r"---
- name: bond99
  type: bond
  state: up
",
    )
    .unwrap();
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
- name: bond99
  link-aggregation:
    mode: balance-rr
",
    )
    .unwrap();
    let merged_iface = MergedInterfaces::new(
        desired.clone(),
        current,
        Default::default(),
        false,
    )
    .unwrap();

    let iface = merged_iface
        .get_iface("bond99", InterfaceType::Bond)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    if let Interface::Bond(iface) = iface {
        assert_eq!(
            iface.bond.as_ref().unwrap().mode,
            Some(BondMode::RoundRobin)
        );
    } else {
        panic!("Should be resolved to bond interface, but got {desired:?}");
    }
}

#[test]
fn test_ifaces_ignore_iface_in_desire() {
    let current = serde_yaml::from_str::<Interfaces>(
        r"---
- name: eth1
  type: ethernet
  state: up
- name: br0
  type: ovs-bridge
  state: up
",
    )
    .unwrap();
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
- name: eth1
  type: ethernet
  state: ignore
- name: br0
  type: ovs-bridge
  state: ignore
",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    let mut ignored_ifaces = merged_ifaces.ignored_ifaces;
    ignored_ifaces.sort_unstable();

    assert_eq!(
        ignored_ifaces[0],
        ("br0".to_string(), InterfaceType::OvsBridge)
    );
    assert_eq!(
        ignored_ifaces[1],
        ("eth1".to_string(), InterfaceType::Ethernet)
    );
}

#[test]
fn test_ifaces_iface_in_unknown_state() {
    let current = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
  - name: eth2
    type: ethernet
    state: up",
    )
    .unwrap();
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
  - name: eth2
    type: ethernet
    state: unknown",
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        desired,
        current,
        crate::NetworkStateMode::Apply,
        false,
    )
    .unwrap();

    assert!(
        merged_ifaces
            .get_iface("eth1", InterfaceType::Ethernet)
            .unwrap()
            .for_apply
            .is_some(),
        "eth1 should have for apply value"
    );
    assert!(
        merged_ifaces
            .get_iface("eth2", InterfaceType::Ethernet)
            .unwrap()
            .for_apply
            .is_none(),
        "eth2 should be purged"
    );
}

#[test]
fn test_ifaces_ignore_iface_in_current() {
    let current = serde_yaml::from_str::<Interfaces>(
        r"---
- name: eth1
  type: ethernet
  state: ignore
- name: br0
  type: ovs-bridge
  state: up
",
    )
    .unwrap();
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
- name: br0
  type: ovs-bridge
  state: ignore
",
    )
    .unwrap();
    let merged_ifaces =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    let mut ignored_ifaces = merged_ifaces.ignored_ifaces;
    ignored_ifaces.sort_unstable();

    assert_eq!(
        ignored_ifaces[0],
        ("br0".to_string(), InterfaceType::OvsBridge)
    );
    assert_eq!(
        ignored_ifaces[1],
        ("eth1".to_string(), InterfaceType::Ethernet)
    );
}

#[test]
fn test_ifaces_ignore_iface_in_current_but_desired() {
    let current = serde_yaml::from_str::<Interfaces>(
        r"---
- name: eth1
  type: ethernet
  state: ignore
- name: eth2
  type: ethernet
  state: up
- name: br0
  type: ovs-bridge
  state: up
",
    )
    .unwrap();
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
- name: eth1
  type: ethernet
  state: down
- name: eth2
  type: ethernet
  state: ignore
- name: br0
  type: ovs-bridge
  state: ignore
",
    )
    .unwrap();
    let merged_ifaces =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    let mut ignored_ifaces = merged_ifaces.ignored_ifaces;
    ignored_ifaces.sort_unstable();

    assert_eq!(ignored_ifaces.len(), 2);
    assert_eq!(
        ignored_ifaces[0],
        ("br0".to_string(), InterfaceType::OvsBridge)
    );
    assert_eq!(
        ignored_ifaces[1],
        ("eth2".to_string(), InterfaceType::Ethernet)
    );
}

#[test]
fn test_ifaces_iter() {
    let ifaces = serde_yaml::from_str::<Interfaces>(
        r"---
- name: eth1
  type: ethernet
  state: ignore
- name: br0
  type: ovs-bridge
  state: up
",
    )
    .unwrap();
    let ifaces_vec: Vec<&Interface> = ifaces.iter().collect();
    assert_eq!(ifaces_vec.len(), 2);
}

#[test]
fn test_ifaces_iter_mut() {
    let mut ifaces = serde_yaml::from_str::<Interfaces>(
        r"---
- name: eth1
  type: ethernet
  state: ignore
- name: br0
  type: ovs-bridge
  state: up
",
    )
    .unwrap();
    for iface in ifaces.iter_mut() {
        iface.base_iface_mut().mtu = Some(1280);
    }
    let ifaces_vec: Vec<&Interface> = ifaces.iter().collect();
    assert_eq!(ifaces_vec.len(), 2);
    assert_eq!(ifaces_vec[0].base_iface().mtu, Some(1280));
    assert_eq!(ifaces_vec[1].base_iface().mtu, Some(1280));
}

#[test]
fn test_unknown_iface_type() {
    assert_eq!(
        InterfaceType::Other("foo_type".to_string()).to_string(),
        "foo_type"
    );
    assert_eq!(
        serde_yaml::to_string(&InterfaceType::Other("foo_type".to_string()))
            .unwrap(),
        "foo_type\n"
    );
}

#[test]
fn test_hsr_mac_sync_no_mac_addresses_defined() {
    let cur_ifaces = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
    mac-address: AA:BB:CC:DD:EE:FF
  - name: eth2
    type: ethernet
    state: up
    ",
    )
    .unwrap();

    let des_ifaces = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
  - name: eth2
    type: ethernet
    state: up
  - name: hsr0
    type: hsr
    state: up
    hsr:
      port1: eth1
      port2: eth2
      multicast-spec: 40
      protocol: prp
",
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        cur_ifaces,
        crate::NetworkStateMode::Apply,
        false,
    )
    .unwrap();

    let hsr_iface =
        merged_ifaces.get_iface("hsr0", InterfaceType::Hsr).unwrap();
    assert_eq!(
        get_mac(&hsr_iface.for_apply),
        Some("AA:BB:CC:DD:EE:FF".to_string())
    );

    let port2_iface = merged_ifaces
        .get_iface("eth2", InterfaceType::Ethernet)
        .unwrap();
    assert_eq!(
        get_mac(&port2_iface.for_apply),
        Some("AA:BB:CC:DD:EE:FF".to_string())
    );
}

#[test]
fn test_hsr_mac_sync_mac_address_defined() {
    let cur_ifaces = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
    mac-address: aa:bb:cc:dd:ee:ff
  - name: eth2
    type: ethernet
    state: up
    mac-address: bb:cc:dd:ee:ff:00
    ",
    )
    .unwrap();

    let des_ifaces = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
  - name: eth2
    type: ethernet
    state: up
  - name: hsr0
    type: hsr
    state: up
    mac-address: bb:cc:ee:ff:00:11
    hsr:
      port1: eth1
      port2: eth2
      multicast-spec: 40
      protocol: prp
",
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        cur_ifaces,
        crate::NetworkStateMode::Apply,
        false,
    )
    .unwrap();

    let hsr_iface =
        merged_ifaces.get_iface("hsr0", InterfaceType::Hsr).unwrap();
    assert_eq!(
        hsr_iface
            .for_apply
            .as_ref()
            .unwrap()
            .base_iface()
            .mac_address,
        Some("BB:CC:EE:FF:00:11".to_string())
    );

    let port1_iface = merged_ifaces
        .get_iface("eth1", InterfaceType::Ethernet)
        .unwrap();
    assert_eq!(
        get_mac(&port1_iface.for_apply),
        Some("BB:CC:EE:FF:00:11".to_string())
    );

    let port2_iface = merged_ifaces
        .get_iface("eth2", InterfaceType::Ethernet)
        .unwrap();
    assert_eq!(
        get_mac(&port2_iface.for_apply),
        Some("BB:CC:EE:FF:00:11".to_string())
    );
}

#[test]
fn test_hsr_conflicting_desired_port_macs() {
    let current = Interfaces::new();
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
    mac-address: 00:23:45:67:89:1a
    ipv4:
      enabled: false
    ipv6:
      enabled: false
  - name: eth2
    type: ethernet
    state: up
    mac-address: 00:23:45:67:89:1b
    ipv4:
      enabled: false
    ipv6:
      enabled: false
  - name: hsr0
    type: hsr
    state: up
    hsr:
      port1: eth1
      port2: eth2
      multicast-spec: 40
      protocol: prp
",
    )
    .unwrap();

    let merged_err =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap_err();
    assert_eq!(merged_err.kind(), ErrorKind::InvalidArgument);
    assert!(merged_err.msg().contains("ports on interface hsr0"));
}

#[test]
fn test_hsr_both_port_desired_macs() {
    let current = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
  - name: eth2
    type: ethernet
    state: up
    ",
    )
    .unwrap();
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
    mac-address: 00:23:45:67:89:1b
    ipv4:
      enabled: false
    ipv6:
      enabled: false
  - name: eth2
    type: ethernet
    state: up
    mac-address: 00:23:45:67:89:1b
    ipv4:
      enabled: false
    ipv6:
      enabled: false
  - name: hsr0
    type: hsr
    state: up
    hsr:
      port1: eth1
      port2: eth2
      multicast-spec: 40
      protocol: prp
",
    )
    .unwrap();

    let merged =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    let port1_iface =
        merged.get_iface("eth1", InterfaceType::Ethernet).unwrap();

    let hsr_iface = merged.get_iface("hsr0", InterfaceType::Ethernet).unwrap();

    assert_eq!(
        get_mac(&port1_iface.for_apply),
        Some("00:23:45:67:89:1B".to_string())
    );
    assert_eq!(
        get_mac(&hsr_iface.for_apply),
        Some("00:23:45:67:89:1B".to_string())
    );
}

#[test]
fn test_hsr_all_ifaces_desired_macs() {
    let current = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
  - name: eth2
    type: ethernet
    state: up
    ",
    )
    .unwrap();
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
    mac-address: 00:23:45:67:89:1c
    ipv4:
      enabled: false
    ipv6:
      enabled: false
  - name: eth2
    type: ethernet
    state: up
    mac-address: 00:23:45:67:89:1c
    ipv4:
      enabled: false
    ipv6:
      enabled: false
  - name: hsr0
    type: hsr
    state: up
    mac-address: 00:23:45:67:89:1c
    hsr:
      port1: eth1
      port2: eth2
      multicast-spec: 40
      protocol: prp
",
    )
    .unwrap();

    let merged =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    let port1_iface =
        merged.get_iface("eth1", InterfaceType::Ethernet).unwrap();

    let hsr_iface = merged.get_iface("hsr0", InterfaceType::Ethernet).unwrap();

    assert_eq!(
        get_mac(&port1_iface.for_apply),
        Some("00:23:45:67:89:1C".to_string())
    );
    assert_eq!(
        get_mac(&hsr_iface.for_apply),
        Some("00:23:45:67:89:1C".to_string())
    );
}

#[test]
fn test_hsr_port2_desired_mac() {
    let current = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    permanent-mac-address: 00:23:45:67:89:1c
    state: up
  - name: eth2
    type: ethernet
    state: up
    ",
    )
    .unwrap();
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
    ipv4:
      enabled: false
    ipv6:
      enabled: false
  - name: eth2
    type: ethernet
    state: up
    mac-address: aa:bb:cc:dd:ee:ff
    ipv4:
      enabled: false
    ipv6:
      enabled: false
  - name: hsr0
    type: hsr
    state: up
    hsr:
      port1: eth1
      port2: eth2
      multicast-spec: 40
      protocol: prp
",
    )
    .unwrap();

    let merged =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    let port1_iface =
        merged.get_iface("eth1", InterfaceType::Ethernet).unwrap();

    let hsr_iface = merged.get_iface("hsr0", InterfaceType::Ethernet).unwrap();

    assert_eq!(
        get_mac(&port1_iface.for_apply),
        Some("AA:BB:CC:DD:EE:FF".to_string())
    );
    assert_eq!(
        get_mac(&hsr_iface.for_apply),
        Some("AA:BB:CC:DD:EE:FF".to_string())
    );
}

#[test]
fn test_hsr_all_ifaces_only_permanent_mac() {
    let current = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    permanent-mac-address: aa:bb:cc:dd:ee:ff
    state: up
  - name: eth2
    type: ethernet
    permanent-mac-address: 11:22:33:44:55:66
    state: up
    ",
    )
    .unwrap();
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
  - name: eth1
    type: ethernet
    state: up
  - name: eth2
    type: ethernet
    state: up
  - name: hsr0
    type: hsr
    state: up
    hsr:
      port1: eth1
      port2: eth2
      multicast-spec: 40
      protocol: prp
",
    )
    .unwrap();

    let merged =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    let port1_iface =
        merged.get_iface("eth1", InterfaceType::Ethernet).unwrap();
    let port2_iface =
        merged.get_iface("eth2", InterfaceType::Ethernet).unwrap();
    let hsr_iface = merged.get_iface("hsr0", InterfaceType::Ethernet).unwrap();

    assert_eq!(
        get_mac(&port1_iface.for_apply),
        Some("AA:BB:CC:DD:EE:FF".to_string())
    );
    assert_eq!(
        get_mac(&port2_iface.for_apply),
        Some("AA:BB:CC:DD:EE:FF".to_string())
    );
    assert_eq!(
        get_mac(&hsr_iface.for_apply),
        Some("AA:BB:CC:DD:EE:FF".to_string())
    );
}
