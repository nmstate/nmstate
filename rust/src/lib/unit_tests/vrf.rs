// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, InterfaceType, Interfaces, MergedInterfaces, VrfInterface,
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

    assert_eq!(iface.vrf.unwrap().table_id, 101);
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

#[test]
fn test_vrf_inconsistent_ports_and_ports_config() {
    let mut des_ifaces: VrfInterface = serde_yaml::from_str(
        r"---
        name: vrf1
        type: vrf
        state: up
        vrf:
          route-table-id: 101
          ports:
            - eth1
            - eth2
          ports-config:
            - name: eth3
            - name: eth1
            - name: eth2
        ",
    )
    .unwrap();

    let result = des_ifaces.sanitize(true);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_unify_ports_and_ports_config() {
    let mut des_ifaces: VrfInterface = serde_yaml::from_str(
        r"---
        name: vrf1
        type: vrf
        state: up
        vrf:
          route-table-id: 101
          ports-config:
            - name: eth3
            - name: eth1
            - name: eth2
        ",
    )
    .unwrap();

    des_ifaces.sanitize(true).unwrap();

    assert_eq!(
        des_ifaces.vrf.as_ref().and_then(|v| v.port.as_deref()),
        Some(
            ["eth1".to_string(), "eth2".to_string(), "eth3".to_string()]
                .as_slice()
        )
    );

    let mut des_ifaces: VrfInterface = serde_yaml::from_str(
        r"---
        name: vrf1
        type: vrf
        state: up
        vrf:
          route-table-id: 101
          ports:
            - eth3
            - eth1
            - eth2
        ",
    )
    .unwrap();

    des_ifaces.sanitize(true).unwrap();

    assert_eq!(
        des_ifaces
            .vrf
            .as_ref()
            .and_then(|v| v.ports_config.as_deref())
            .map(|ports_config| ports_config
                .iter()
                .map(|p| p.name.clone())
                .collect()),
        Some(vec![
            Some("eth1".to_string()),
            Some("eth2".to_string()),
            Some("eth3".to_string())
        ])
    );
}

#[test]
fn test_vrf_resolve_port_ref_by_profile_name() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: eth1
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1a",
    )
    .unwrap();
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: vrf0-port1
          type: ethernet
          state: up
          identifier: mac-address
          mac-address: 00:23:45:67:89:1a
        - name: vrf0
          type: vrf
          state: up
          vrf:
            route-table-id: 100
            ports-config:
            - profile-name: vrf0-port1",
    )
    .unwrap();
    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();

    assert_eq!(
        merged_ifaces
            .kernel_ifaces
            .get("vrf0")
            .unwrap()
            .desired
            .as_ref()
            .unwrap()
            .ports(),
        Some(vec!["eth1"])
    );
}
