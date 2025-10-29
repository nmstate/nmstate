// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, InterfaceType, Interfaces, MergedInterfaces, Routes,
    VrfInterface,
};

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

    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        cur_ifaces,
        Default::default(),
        false,
    )
    .unwrap();

    let iface = merged_ifaces
        .get_iface("test-bond0.100", InterfaceType::Vlan)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    assert!(iface.is_absent());
}

#[test]
fn test_vrf_skip_port_if_null() {
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

    let iface_yaml = serde_yaml::to_string(&iface).unwrap();

    assert!(!iface_yaml.contains("port"))
}

#[test]
fn test_route_vrf_name() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: vrf0
          type: vrf
          state: up
          vrf:
            route-table-id: 100
        ",
    )
    .unwrap();

    let des_ifaces = Interfaces::default();

    let mut des_routes: Routes = serde_yaml::from_str(
        r"---
        config:
          - destination: 198.51.200.0/24
            route-type: blackhole
            vrf-name: vrf0
        ",
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        cur_ifaces,
        Default::default(),
        false,
    )
    .unwrap();

    des_routes.resolve_vrf_name(&merged_ifaces).unwrap();

    assert_eq!(des_routes.config.as_ref().unwrap()[0].table_id, Some(100));
}

#[test]
fn test_route_vrf_name_down() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: vrf0
          type: vrf
          state: up
          vrf:
            route-table-id: 100
        ",
    )
    .unwrap();

    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: vrf0
          type: vrf
          state: down
        ",
    )
    .unwrap();

    let mut des_routes: Routes = serde_yaml::from_str(
        r"---
        config:
          - destination: 198.51.200.0/24
            route-type: blackhole
            vrf-name: vrf0
        ",
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        cur_ifaces,
        Default::default(),
        false,
    )
    .unwrap();

    let result = des_routes.resolve_vrf_name(&merged_ifaces);
    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_route_vrf_name_absent() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: vrf0
          type: vrf
          state: up
          vrf:
            route-table-id: 100
        ",
    )
    .unwrap();

    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: vrf0
          type: vrf
          state: absent
        ",
    )
    .unwrap();

    let mut des_routes: Routes = serde_yaml::from_str(
        r"---
        config:
          - destination: 198.51.200.0/24
            route-type: blackhole
            vrf-name: vrf0
        ",
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        cur_ifaces,
        Default::default(),
        false,
    )
    .unwrap();

    let result = des_routes.resolve_vrf_name(&merged_ifaces);
    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_route_vrf_name_table_id_conflict() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: vrf0
          type: vrf
          state: up
          vrf:
            route-table-id: 100
        ",
    )
    .unwrap();

    let des_ifaces = Interfaces::default();

    let mut des_routes: Routes = serde_yaml::from_str(
        r"---
        config:
          - destination: 198.51.200.0/24
            route-type: blackhole
            table-id: 101
            vrf-name: vrf0
        ",
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        cur_ifaces,
        Default::default(),
        false,
    )
    .unwrap();

    let result = des_routes.resolve_vrf_name(&merged_ifaces);
    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}
