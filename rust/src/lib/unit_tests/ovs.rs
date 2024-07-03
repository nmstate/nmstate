// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, Interface, InterfaceType, Interfaces, MergedInterface,
    MergedInterfaces, OvsBridgeInterface, OvsInterface,
};

#[test]
fn test_ovs_bridge_ignore_port() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
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
  bridge:
    port:
    - name: eth2
",
    )
    .unwrap();
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: eth1
  type: ethernet
  state: up
- name: eth2
  type: ethernet
  state: up
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: eth2
",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();

    let mut ignored_ifaces = merged_ifaces.ignored_ifaces.clone();
    ignored_ifaces.sort_unstable();
    assert_eq!(
        ignored_ifaces[0],
        ("eth1".to_string(), InterfaceType::Ethernet)
    );

    let eth2_iface = merged_ifaces
        .get_iface("eth2", InterfaceType::Ethernet)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    let br0_iface = merged_ifaces
        .get_iface("br0", InterfaceType::OvsBridge)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(br0_iface.ports(), Some(vec!["eth2"]));

    // eth2 should hold no changes to controller
    assert_eq!(eth2_iface.base_iface().controller, None);
    assert_eq!(eth2_iface.base_iface().controller_type, None);
}

#[test]
fn test_ovs_bridge_verify_ignore_port() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: eth1
  type: ethernet
  state: ignore
- name: eth2
  type: ethernet
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth2
",
    )
    .unwrap();
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: eth1
  type: ethernet
  state: up
- name: eth2
  type: ethernet
  state: up
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: eth2
",
    )
    .unwrap();

    let pre_apply_cur_ifaces: Interfaces = serde_yaml::from_str(
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

    let merged_iface =
        MergedInterfaces::new(des_ifaces, pre_apply_cur_ifaces, false, false)
            .unwrap();

    merged_iface.verify(&cur_ifaces).unwrap();
}

#[test]
fn test_ovs_bridge_stringlized_attributes() {
    let iface: OvsBridgeInterface = serde_yaml::from_str(
        r#"---
name: br1
type: ovs-bridge
state: up
bridge:
  options:
    stp: "true"
    rstp: "false"
    mcast-snooping-enable: "false"
  port:
  - name: bond1
    link-aggregation:
      bond-downdelay: "100"
      bond-updelay: "101"
"#,
    )
    .unwrap();

    let br_conf = iface.bridge.unwrap();
    let opts = br_conf.options.as_ref().unwrap();
    let port_conf = &br_conf.ports.as_ref().unwrap()[0];
    let bond_conf = port_conf.bond.as_ref().unwrap();
    assert_eq!(opts.stp.as_ref().and_then(|s| s.enabled), Some(true));
    assert_eq!(opts.rstp, Some(false));
    assert_eq!(opts.mcast_snooping_enable, Some(false));
    assert_eq!(bond_conf.bond_downdelay, Some(100));
    assert_eq!(bond_conf.bond_updelay, Some(101));
}

#[test]
fn test_ovs_bridge_same_name_absent() {
    let current: Interfaces = serde_yaml::from_str(
        r"---
- name: eth1
  type: ethernet
- name: br1
  type: ovs-interface
- name: br1
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: br1
    - name: eth1
",
    )
    .unwrap();

    let desired: Interfaces = serde_yaml::from_str(
        r"---
- name: br1
  type: ovs-bridge
  state: absent
",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let br1_iface = merged_ifaces
        .get_iface("br1", InterfaceType::OvsBridge)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    let br1_ovs_iface = merged_ifaces
        .get_iface("br1", InterfaceType::OvsInterface)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    let eth1_iface = merged_ifaces
        .get_iface("eth1", InterfaceType::Ethernet)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert!(br1_iface.is_absent());
    assert!(br1_ovs_iface.is_absent());
    assert_eq!(eth1_iface.base_iface().controller.as_deref(), Some(""));
}

#[test]
fn test_ovs_bridge_resolve_user_space_iface_type() {
    let current: Interfaces = serde_yaml::from_str(
        r"---
- name: br1
  type: ovs-interface
- name: ovs-br1
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: br1
",
    )
    .unwrap();

    let desired: Interfaces = serde_yaml::from_str(
        r"---
- name: ovs-br1
  state: absent
",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let iface = merged_ifaces
        .get_iface("ovs-br1", InterfaceType::OvsBridge)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert!(iface.is_absent());
    assert_eq!(iface.iface_type(), InterfaceType::OvsBridge);
}

#[test]
fn test_ovs_bridge_ports() {
    let ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    ports:
    - name: eth1
    - name: eth2
    - name: bond1
      link-aggregation:
        mode: balance-slb
        ports:
          - name: eth3
          - name: eth4
",
    )
    .unwrap();
    assert_eq!(
        ifaces.to_vec()[0].ports(),
        Some(vec!["eth1", "eth2", "eth3", "eth4"])
    );
}

#[test]
fn test_ovs_bridge_merge_port_vlan() {
    let cur_iface: Interface = serde_yaml::from_str(
        r#"---
name: br0
type: ovs-bridge
state: up
bridge:
  port:
  - name: eth1
    vlan:
      enable-native: "true"
      tag: "102"
      trunk-tags:
      - id: "103"
      - id-range:
          max: "1024"
          min: "105"
  - name: eth2
    vlan:
      enable-native: "true"
      tag: "202"
      trunk-tags:
      - id: "203"
      - id-range:
          max: "2024"
          min: "1025"
"#,
    )
    .unwrap();

    let des_iface: Interface = serde_yaml::from_str(
        r"---
name: br0
type: ovs-bridge
state: up
bridge:
  port:
  - name: eth1
  - name: eth2
",
    )
    .unwrap();

    let merged_iface =
        MergedInterface::new(Some(des_iface), Some(cur_iface)).unwrap();

    if let Interface::OvsBridge(iface) = &merged_iface.merged {
        for port_conf in iface.bridge.as_ref().unwrap().ports.as_ref().unwrap()
        {
            assert!(port_conf.vlan.is_some());
        }
    } else {
        panic!("Expecting a OvsBridge but got {:?}", merged_iface.merged);
    }
}

#[test]
fn test_ovs_bridge_vlan_filter_trunk_tag_without_enable_native() {
    let mut desired: OvsBridgeInterface = serde_yaml::from_str(
        r"
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
            - name: eth1
              vlan:
                mode: trunk
                tag: 200
                trunk-tags:
                  - id-range:
                      min: 600
                      max: 900
                  - id-range:
                      max: 500
                      min: 400
        ",
    )
    .unwrap();

    let result = desired.sanitize(true);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovs_bridge_vlan_filter_trunk_tag_overlap_id_vs_range() {
    let mut desired: OvsBridgeInterface = serde_yaml::from_str(
        r"
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
            - name: eth1
              vlan:
                mode: trunk
                trunk-tags:
                  - id-range:
                      min: 600
                      max: 900
                  - id: 600
        ",
    )
    .unwrap();

    let result = desired.sanitize(true);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovs_bridge_vlan_filter_trunk_tag_overlap_range_vs_range() {
    let mut desired: OvsBridgeInterface = serde_yaml::from_str(
        r"
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
            - name: eth1
              vlan:
                mode: trunk
                trunk-tags:
                  - id-range:
                      min: 600
                      max: 900
                  - id-range:
                      min: 900
                      max: 1000
        ",
    )
    .unwrap();

    let result = desired.sanitize(true);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovs_bridge_vlan_filter_trunk_tag_overlap_id_vs_id() {
    let mut desired: OvsBridgeInterface = serde_yaml::from_str(
        r"
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
            - name: eth1
              vlan:
                mode: trunk
                trunk-tags:
                  - id: 100
                  - id: 100
        ",
    )
    .unwrap();

    let result = desired.sanitize(true);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovs_bridge_vlan_filter_enable_native_with_access_mode() {
    let mut desired: OvsBridgeInterface = serde_yaml::from_str(
        r"
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
            - name: eth1
              vlan:
                enable-native: true
                mode: access
        ",
    )
    .unwrap();

    let result = desired.sanitize(true);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovs_bridge_vlan_filter_trunk_tags_with_access_mode() {
    let mut desired: OvsBridgeInterface = serde_yaml::from_str(
        r"
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
            - name: eth1
              vlan:
                mode: access
                trunk-tags:
                  - id: 100
        ",
    )
    .unwrap();

    let result = desired.sanitize(true);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovs_bridge_vlan_filter_no_trunk_tags_with_trunk_mode() {
    let mut desired: OvsBridgeInterface = serde_yaml::from_str(
        r"
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
            - name: eth1
              vlan:
                mode: trunk
        ",
    )
    .unwrap();

    let result = desired.sanitize(true);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_validate_dpdk_n_rxq_desc() {
    let desired: OvsInterface = serde_yaml::from_str(
        r"
        name: ovs0
        type: ovs-interface
        state: up
        dpdk:
          devargs: 0000:af:00.1
          n_rxq_desc: 1025
        ",
    )
    .unwrap();

    let result = desired.sanitize(true);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("OVS DPDK n_rxq_desc must power of 2"));
    }
}

#[test]
fn test_validate_dpdk_n_txq_desc() {
    let desired: OvsInterface = serde_yaml::from_str(
        r"
        name: ovs0
        type: ovs-interface
        state: up
        dpdk:
          devargs: 0000:af:00.1
          n_txq_desc: 1025
        ",
    )
    .unwrap();

    let result = desired.sanitize(true);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("OVS DPDK n_txq_desc must power of 2"));
    }
}

#[test]
fn test_ovs_orphan_check_on_bridge_with_same_name_iface() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
              - name: ovs0
        ",
    )
    .unwrap();

    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"
        - name: br0
          type: ovs-interface
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
              - name: br0
        ",
    )
    .unwrap();

    MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();
}

#[test]
fn test_ovs_mark_orphan_up_on_bridge_with_same_name_iface() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"
        - name: br0
          type: ovs-interface
          state: up
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
              - name: ovs0
        ",
    )
    .unwrap();

    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"
        - name: br0
          type: ovs-interface
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
              - name: br0
        ",
    )
    .unwrap();

    MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();
}

#[test]
fn test_ignore_patch_ports_for_verify() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: eth1
  type: ethernet
- name: eth2
  type: ethernet
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    allow-extra-patch-ports: true
    port:
    - name: eth1
- name: br1
  type: ovs-bridge
  state: up
  bridge:
    allow-extra-patch-ports: true
    port:
    - name: eth2
",
    )
    .unwrap();
    let pre_apply_cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: eth1
  type: ethernet
  state: up
- name: eth2
  type: ethernet
  state: up
- name: patch0
  type: ovs-interface
  state: up
  controller: br0
  lldp:
    enabled: false
  patch:
    peer: patch1
- name: patch1
  type: ovs-interface
  state: up
  controller: br1
  lldp:
    enabled: false
  patch:
    peer: patch0
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: patch0
- name: br1
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: patch1
",
    )
    .unwrap();

    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: eth1
  type: ethernet
  state: up
- name: eth2
  type: ethernet
  state: up
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: patch0
- name: patch0
  type: ovs-interface
  state: up
  controller: br0
  lldp:
    enabled: false
  patch:
    peer: patch1
- name: br1
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth2
    - name: patch1
- name: patch1
  type: ovs-interface
  state: up
  controller: br1
  lldp:
    enabled: false
  patch:
    peer: patch0
",
    )
    .unwrap();

    let merged_iface =
        MergedInterfaces::new(des_ifaces, pre_apply_cur_ifaces, false, false)
            .unwrap();

    merged_iface.verify(&cur_ifaces).unwrap();
}

#[test]
fn test_ignore_patch_ports_for_apply() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: eth1
  type: ethernet
- name: eth2
  type: ethernet
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    allow-extra-patch-ports: true
    port:
    - name: eth1
- name: br1
  type: ovs-bridge
  state: up
  bridge:
    allow-extra-patch-ports: true
    port:
    - name: eth2
",
    )
    .unwrap();
    let pre_apply_cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: eth1
  type: ethernet
  state: up
- name: eth2
  type: ethernet
  state: up
- name: patch0
  type: ovs-interface
  state: up
  controller: br0
  lldp:
    enabled: false
  patch:
    peer: patch1
- name: patch1
  type: ovs-interface
  state: up
  controller: br1
  lldp:
    enabled: false
  patch:
    peer: patch0
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: patch0
- name: br1
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: patch1
",
    )
    .unwrap();

    let merged_iface =
        MergedInterfaces::new(des_ifaces, pre_apply_cur_ifaces, false, false)
            .unwrap();

    let patch0_iface = merged_iface
        .get_iface("patch0", InterfaceType::OvsInterface)
        .unwrap();
    let patch1_iface = merged_iface
        .get_iface("patch1", InterfaceType::OvsInterface)
        .unwrap();

    assert!(patch0_iface.for_apply.is_none());
    assert!(patch1_iface.for_apply.is_none());
}

#[test]
fn test_ovs_stp_option_as_dict() {
    let iface: OvsBridgeInterface = serde_yaml::from_str(
        r"---
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
          - name: eth1
          options:
            stp:
              enabled: true",
    )
    .unwrap();

    assert_eq!(
        iface
            .bridge
            .as_ref()
            .unwrap()
            .options
            .as_ref()
            .unwrap()
            .stp
            .as_ref()
            .unwrap()
            .enabled,
        Some(true)
    );

    // Make sure we are using new-dict format when serializing
    assert!(!serde_json::to_string(&iface).unwrap().contains("stp: true"));
}

#[test]
fn test_ovs_stp_option_as_bool() {
    let iface: OvsBridgeInterface = serde_yaml::from_str(
        r"---
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
          - name: eth1
          options:
            stp: true",
    )
    .unwrap();

    assert_eq!(
        iface
            .bridge
            .as_ref()
            .unwrap()
            .options
            .as_ref()
            .unwrap()
            .stp
            .as_ref()
            .unwrap()
            .enabled,
        Some(true)
    );
}

#[test]
fn test_ovs_iface_serialize_allow_extra_patch_ports() {
    let desired: OvsBridgeInterface = serde_yaml::from_str(
        r#"---
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          allow-extra-patch-ports: true
          port:
          - name: ovs0
          - name: eth1
        "#,
    )
    .unwrap();

    let new: OvsBridgeInterface =
        serde_yaml::from_str(&serde_yaml::to_string(&desired).unwrap())
            .unwrap();

    assert_eq!(desired, new);
}

#[test]
fn test_ovs_bridge_with_mac() {
    let mut desired: OvsBridgeInterface = serde_yaml::from_str(
        r"
        name: br0
        type: ovs-bridge
        state: up
        mac-address: 05:04:03:02:01:00
        bridge:
          port:
            - name: eth1
            - name: ovs1
        ",
    )
    .unwrap();

    let result = desired.sanitize(true);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovs_bridge_resolve_port_ref_by_profile_name() {
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
        - name: br0-port1
          type: ethernet
          state: up
          identifier: mac-address
          mac-address: 00:23:45:67:89:1a
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            ports:
            - profile-name: br0-port1",
    )
    .unwrap();
    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();

    assert_eq!(
        merged_ifaces
            .user_ifaces
            .get(&("br0".to_string(), InterfaceType::OvsBridge))
            .unwrap()
            .desired
            .as_ref()
            .unwrap()
            .ports(),
        Some(vec!["eth1"])
    );
}

#[test]
fn test_ovs_bridge_resolve_bond_port_ref_by_profile_name() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: eth1
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1a
        - name: eth2
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1b",
    )
    .unwrap();
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: br0-port1
          type: ethernet
          state: up
          identifier: mac-address
          mac-address: 00:23:45:67:89:1a
        - name: br0-port2
          type: ethernet
          state: up
          identifier: mac-address
          mac-address: 00:23:45:67:89:1B
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            ports:
            - name: br0-bond0
              link-aggregation:
                  mode: balance-slb
                  ports:
                  - profile-name: br0-port1
                  - profile-name: br0-port2",
    )
    .unwrap();
    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();

    assert_eq!(
        merged_ifaces
            .user_ifaces
            .get(&("br0".to_string(), InterfaceType::OvsBridge))
            .unwrap()
            .desired
            .as_ref()
            .unwrap()
            .ports(),
        Some(vec!["eth1", "eth2"])
    );
}

#[test]
fn test_ovs_bridge_validate_interface_name_and_profile_name_missmatch() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: eth1
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1a
        - name: eth2
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1b",
    )
    .unwrap();
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: br0-port1
          type: ethernet
          state: up
          identifier: mac-address
          mac-address: 00:23:45:67:89:1a
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            ports:
            - profile-name: br0-port1
              name: eth2",
    )
    .unwrap();
    let result = MergedInterfaces::new(des_ifaces, cur_ifaces, false, false);

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovs_bridge_bond_validate_interface_name_and_profile_name_missmatch() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: eth1
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1a
        - name: eth2
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1b",
    )
    .unwrap();
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: br0-port1
          type: ethernet
          state: up
          identifier: mac-address
          mac-address: 00:23:45:67:89:1a
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            ports:
            - name: br0-bond0
              link-aggregation:
                  mode: balance-slb
                  ports:
                  - profile-name: br0-port1
                    name: eth2",
    )
    .unwrap();
    let result = MergedInterfaces::new(des_ifaces, cur_ifaces, false, false);

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}
