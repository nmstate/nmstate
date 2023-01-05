// SPDX-License-Identifier: Apache-2.0

use crate::{InterfaceType, Interfaces, MergedInterfaces, VlanInterface};

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
