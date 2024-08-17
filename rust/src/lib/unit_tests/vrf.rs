// SPDX-License-Identifier: Apache-2.0

use crate::{InterfaceType, Interfaces, MergedInterfaces, VrfInterface};

#[test]
fn test_vrf_stringlized_attributes() {
    let iface: VrfInterface = serde_yaml::from_str(
        r#"---
name: vrf1
type: vrf
state: up
vrf:
  route-table-id: "101"
"#,
    )
    .unwrap();

    assert_eq!(iface.vrf.unwrap().table_id, Some(101));
}

#[test]
fn test_vrf_ports() {
    let ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: vrf1
  type: vrf
  state: up
  vrf:
    route-table-id: "101"
    ports:
      - eth1
      - eth2
"#,
    )
    .unwrap();

    assert_eq!(ifaces.to_vec()[0].ports(), Some(vec!["eth1", "eth2"]));
}

#[test]
fn test_vrf_on_bond_vlan_got_auto_remove() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: test-bond0.100
          type: vlan
          vlan:
            base-iface: test-bond0
            id: 100
        - name: test-bond0
          type: bond
          link-aggregation:
            mode: balance-rr
        - name: test-vrf0
          type: vrf
          state: up
          vrf:
            port:
            - test-bond0
            - test-bond0.100
            route-table-id: 100
        ",
    )
    .unwrap();

    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: test-bond0
          type: bond
          state: absent
        - name: test-vrf0
          type: vrf
          state: absent
        ",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();

    let iface = merged_ifaces
        .get_iface("test-bond0.100", InterfaceType::Vlan)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    assert!(iface.is_absent());
}
