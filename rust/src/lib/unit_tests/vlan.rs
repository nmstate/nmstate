// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, InterfaceType, Interfaces, MergedInterfaces, VlanInterface,
    VlanProtocol,
};

#[test]
fn test_vlan_stringlized_attributes() {
    let iface: VlanInterface = serde_yaml::from_str(
        r#"---
name: vlan1
type: vlan
state: up
vlan:
  base-iface: "eth1"
  id: "101"
"#,
    )
    .unwrap();

    assert_eq!(iface.vlan.unwrap().id, 101);
}

#[test]
fn test_vlan_get_parent_up_priority_plus_one() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: bond0.100
  type: vlan
  vlan:
    base-iface: bond0
    id: 100
- name: bond0
  type: bond
  link-aggregation:
    mode: balance-rr
- name: vrf0
  type: vrf
  state: up
  vrf:
    port:
    - bond0
    - bond0.100
    route-table-id: 1000"#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, Interfaces::new(), false, false)
            .unwrap();

    let vrf0_iface = merged_ifaces
        .get_iface("vrf0", InterfaceType::Vrf)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    let bond0_iface = merged_ifaces
        .get_iface("bond0", InterfaceType::Bond)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    let vlan_iface = merged_ifaces
        .get_iface("bond0.100", InterfaceType::Vlan)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(vrf0_iface.base_iface().up_priority, 0);
    assert_eq!(bond0_iface.base_iface().up_priority, 1);
    assert_eq!(vlan_iface.base_iface().up_priority, 2);
}

#[test]
fn test_vlan_orphan_check_auto_absent() {
    let current: Interfaces = serde_yaml::from_str(
        r#"---
        - name: bond0.100
          type: vlan
          vlan:
            base-iface: bond0
            id: 100
        - name: bond0
          type: bond
          link-aggregation:
            mode: balance-rr"#,
    )
    .unwrap();
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
        - name: bond0
          type: bond
          state: absent"#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let vlan_iface = merged_ifaces
        .get_iface("bond0.100", InterfaceType::Vlan)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert!(vlan_iface.is_absent())
}

#[test]
fn test_vlan_orphan_but_desired() {
    let current: Interfaces = serde_yaml::from_str(
        r#"---
        - name: bond0.100
          type: vlan
          vlan:
            base-iface: bond0
            id: 100
        - name: bond0
          type: bond
          link-aggregation:
            mode: balance-rr"#,
    )
    .unwrap();
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
        - name: bond0.100
        - name: bond0
          type: bond
          state: absent"#,
    )
    .unwrap();

    let result = MergedInterfaces::new(desired, current, false, false);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains(
            "Interface bond0.100 cannot be in up state \
            as its parent bond0 has been marked as absent"
        ));
    }
}

#[test]
fn test_vlan_orphan_has_now_parent() {
    let current: Interfaces = serde_yaml::from_str(
        r#"---
        - name: bond0.100
          type: vlan
          vlan:
            base-iface: bond0
            id: 100
        - name: bond0
          type: bond
          link-aggregation:
            mode: balance-rr"#,
    )
    .unwrap();
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
        - name: bond0.100
          state: up
          type: vlan
          vlan:
            base-iface: bond1
            id: 100
        - name: bond1
          type: bond
          state: up
          link-aggregation:
            mode: balance-rr
        - name: bond0
          type: bond
          state: absent"#,
    )
    .unwrap();

    MergedInterfaces::new(desired, current, false, false).unwrap();
}

#[test]
fn test_vlan_update() {
    let mut iface1: VlanInterface = serde_yaml::from_str(
        r#"---
        name: bond0.100
        type: vlan
        vlan:
          base-iface: bond0
          id: 100"#,
    )
    .unwrap();

    let iface2: VlanInterface = serde_yaml::from_str(
        r#"---
        name: bond0.100
        type: vlan
        vlan:
          base-iface: bond0
          id: 100
          protocol: 802.1q"#,
    )
    .unwrap();

    iface1.update_vlan(&iface2);

    assert_eq!(
        iface1.vlan.as_ref().unwrap().protocol,
        Some(VlanProtocol::Ieee8021Q)
    );
}
