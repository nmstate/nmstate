// SPDX-License-Identifier: Apache-2.0

use crate::{
    BridgePortTunkTag, BridgePortVlanRange, ErrorKind, Interface,
    InterfaceType, Interfaces, LinuxBridgeInterface,
    LinuxBridgeMulticastRouterType, MergedInterface, MergedInterfaces,
};

#[test]
fn test_linux_bridge_ignore_port() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: ignore
- name: eth2
  type: ethernet
- name: br0
  type: linux-bridge
  state: up
  bridge:
    port:
    - name: eth2
"#,
    )
    .unwrap();
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
- name: eth2
  type: ethernet
  state: up
- name: br0
  type: linux-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: eth2
"#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();

    let ignored_ifaces = merged_ifaces.ignored_ifaces.as_slice();

    assert_eq!(
        ignored_ifaces,
        vec![("eth1".to_string(), InterfaceType::Ethernet)].as_slice()
    );
    let merged_iface = merged_ifaces
        .get_iface("br0", InterfaceType::Ethernet)
        .unwrap();

    let des_iface = merged_iface.desired.as_ref().unwrap();
    let cur_iface = merged_iface.current.as_ref().unwrap();

    assert_eq!(des_iface.ports(), Some(vec!["eth2"]));
    assert_eq!(cur_iface.ports(), Some(vec!["eth2"]));

    assert!(merged_ifaces
        .get_iface("eth1", InterfaceType::Ethernet)
        .is_none());
}

#[test]
fn test_linux_bridge_verify_ignore_port() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: ignore
- name: eth2
  type: ethernet
- name: br0
  type: linux-bridge
  state: up
  bridge:
    port:
    - name: eth2
"#,
    )
    .unwrap();
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
- name: eth2
  type: ethernet
  state: up
- name: br0
  type: linux-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: eth2
"#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces.clone(), false, false)
            .unwrap();
    merged_ifaces.verify(&cur_ifaces).unwrap();
}

#[test]
fn test_linux_bridge_stringlized_attributes() {
    let iface: LinuxBridgeInterface = serde_yaml::from_str(
        r#"---
name: br0
type: linux-bridge
state: up
bridge:
  options:
    group-forward-mask: "300"
    group-fwd-mask: "301"
    hash-max: "302"
    mac-ageing-time: "303"
    multicast-last-member-count: "304"
    multicast-last-member-interval: "305"
    multicast-membership-interval: "306"
    multicast-querier: "1"
    multicast-querier-interval: "307"
    multicast-query-interval: "308"
    multicast-query-response-interval: "309"
    multicast-query-use-ifaddr: "yes"
    multicast-snooping: "no"
    multicast-startup-query-count: "310"
    multicast-startup-query-interval: "311"
    stp:
      enabled: "false"
      forward-delay: "16"
      hello-time: "2"
      max-age: "20"
      priority: "32768"
  port:
  - name: eth1
    stp-hairpin-mode: "false"
    stp-path-cost: "100"
    stp-priority: "101"
    vlan:
      enable-native: "true"
      tag: "102"
      trunk-tags:
      - id: "103"
      - id-range:
          max: "1024"
          min: "105"
"#,
    )
    .unwrap();

    let br_conf = iface.bridge.unwrap();
    let port_conf = &br_conf.port.as_ref().unwrap()[0];
    let vlan_conf = port_conf.vlan.as_ref().unwrap();
    let opts = br_conf.options.as_ref().unwrap();
    let stp_opts = opts.stp.as_ref().unwrap();

    assert_eq!(port_conf.stp_hairpin_mode, Some(false));
    assert_eq!(port_conf.stp_path_cost, Some(100));
    assert_eq!(port_conf.stp_priority, Some(101));
    assert_eq!(vlan_conf.enable_native, Some(true));
    assert_eq!(vlan_conf.tag, Some(102));
    assert_eq!(
        &vlan_conf.trunk_tags.as_ref().unwrap()[0],
        &BridgePortTunkTag::Id(103)
    );
    assert_eq!(
        &vlan_conf.trunk_tags.as_ref().unwrap()[1],
        &BridgePortTunkTag::IdRange(BridgePortVlanRange {
            max: 1024,
            min: 105
        })
    );

    assert_eq!(stp_opts.enabled, Some(false));
    assert_eq!(stp_opts.forward_delay, Some(16));
    assert_eq!(stp_opts.hello_time, Some(2));
    assert_eq!(stp_opts.max_age, Some(20));
    assert_eq!(stp_opts.priority, Some(32768));

    assert_eq!(opts.group_forward_mask, Some(300));
    assert_eq!(opts.group_fwd_mask, Some(301));
    assert_eq!(opts.hash_max, Some(302));
    assert_eq!(opts.mac_ageing_time, Some(303));
    assert_eq!(opts.multicast_last_member_count, Some(304));
    assert_eq!(opts.multicast_last_member_interval, Some(305));
    assert_eq!(opts.multicast_membership_interval, Some(306));
    assert_eq!(opts.multicast_querier, Some(true));
    assert_eq!(opts.multicast_querier_interval, Some(307));
    assert_eq!(opts.multicast_query_interval, Some(308));
    assert_eq!(opts.multicast_query_response_interval, Some(309));
    assert_eq!(opts.multicast_query_use_ifaddr, Some(true));
    assert_eq!(opts.multicast_snooping, Some(false));
    assert_eq!(opts.multicast_startup_query_count, Some(310));
    assert_eq!(opts.multicast_startup_query_interval, Some(311));
}

#[test]
fn test_linux_bridge_partial_ignored() {
    let cur_ifaces = serde_yaml::from_str::<Interfaces>(
        r#"---
- name: eth1
  type: ethernet
  state: ignore
- name: eth2
  type: ethernet
  state: ignore
- name: br0
  type: linux-bridge
  state: ignore
  bridge:
    port:
    - name: eth1
    - name: eth2
"#,
    )
    .unwrap();
    let des_ifaces = serde_yaml::from_str::<Interfaces>(
        r#"---
- name: br0
  type: linux-bridge
  state: up
- name: eth1
  type: ethernet
  state: up
"#,
    )
    .unwrap();
    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();

    let ignored_ifaces = merged_ifaces.ignored_ifaces.as_slice();

    assert_eq!(
        ignored_ifaces,
        vec![("eth2".to_string(), InterfaceType::Ethernet)].as_slice()
    );

    let merged_iface = merged_ifaces
        .get_iface("eth1", InterfaceType::Ethernet)
        .unwrap();

    let apply_iface = merged_iface.for_apply.as_ref().unwrap();

    assert_eq!(apply_iface.base_iface().controller, Some("br0".to_string()));
    assert_eq!(
        apply_iface.base_iface().controller_type,
        Some(InterfaceType::LinuxBridge)
    );
}

#[test]
fn test_linux_bridge_interger_multicast_router() {
    let iface: LinuxBridgeInterface = serde_yaml::from_str(
        r#"---
name: br0
type: linux-bridge
state: up
bridge:
  options:
    multicast-router: 0
"#,
    )
    .unwrap();

    assert_eq!(
        iface
            .bridge
            .unwrap()
            .options
            .as_ref()
            .unwrap()
            .multicast_router,
        Some(LinuxBridgeMulticastRouterType::Disabled)
    );
}

#[test]
fn test_linux_bridge_ports() {
    let ifaces = serde_yaml::from_str::<Interfaces>(
        r#"---
- name: br0
  type: linux-bridge
  state: up
  bridge:
    ports:
    - name: eth1
    - name: eth2
"#,
    )
    .unwrap();
    assert_eq!(ifaces.to_vec()[0].ports(), Some(vec!["eth1", "eth2"]));
}

#[test]
fn test_linux_bridge_partially_disable_vlan_filtering() {
    let current = serde_yaml::from_str::<LinuxBridgeInterface>(
        r#"---
name: br0
type: linux-bridge
state: up
bridge:
  port:
    - name: eth1
      vlan:
        mode: access
        trunk-tags: []
        tag: 305
    - name: eth2
      vlan:
        mode: trunk
        trunk-tags:
        - id: 500
"#,
    )
    .unwrap();
    let desired = serde_yaml::from_str::<LinuxBridgeInterface>(
        r#"---
name: br0
type: linux-bridge
state: up
bridge:
  port:
    - name: eth1
      vlan: {}
    - name: eth2
"#,
    )
    .unwrap();

    assert_eq!(desired.get_config_changed_ports(&current), vec!["eth1"])
}

#[test]
fn test_linux_bridge_vlan_trunk_tags_yaml_serilize() {
    let yml_content = r#"name: br0
type: linux-bridge
state: up
bridge:
  port:
  - name: eth1
    vlan:
      mode: access
      tag: 305
      trunk-tags:
      - id: 101
      - id-range:
          min: 500
          max: 599
  - name: eth2
    vlan:
      mode: trunk
      trunk-tags:
      - id: 500
"#;
    let iface: LinuxBridgeInterface =
        serde_yaml::from_str(yml_content).unwrap();

    assert_eq!(serde_yaml::to_string(&iface).unwrap(), yml_content);
}

#[test]
fn test_linux_bridge_merge_port_vlan() {
    let cur_iface: Interface = serde_yaml::from_str(
        r#"---
name: br0
type: linux-bridge
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
        r#"---
name: br0
type: linux-bridge
state: up
bridge:
  port:
  - name: eth1
  - name: eth2
"#,
    )
    .unwrap();

    let merged_iface =
        MergedInterface::new(Some(des_iface), Some(cur_iface)).unwrap();

    if let Interface::LinuxBridge(iface) = &merged_iface.merged {
        assert!(iface.vlan_filtering_is_enabled());
    } else {
        panic!("Expecting a LinuxBridge but got {:?}", merged_iface.merged);
    }
}

#[test]
fn test_bridge_vlan_filter_trunk_tag_without_enable_native() {
    let mut desired: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            stp:
              enabled: true
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
        "#,
    )
    .unwrap();

    let result = desired.sanitize();

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_bridge_vlan_filter_trunk_tag_overlap_id_vs_range() {
    let mut desired: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            stp:
              enabled: true
          port:
            - name: eth1
              vlan:
                mode: trunk
                trunk-tags:
                  - id-range:
                      min: 600
                      max: 900
                  - id: 600
        "#,
    )
    .unwrap();

    let result = desired.sanitize();

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_bridge_vlan_filter_trunk_tag_overlap_range_vs_range() {
    let mut desired: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            stp:
              enabled: true
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
        "#,
    )
    .unwrap();

    let result = desired.sanitize();

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_bridge_vlan_filter_trunk_tag_overlap_id_vs_id() {
    let mut desired: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            stp:
              enabled: true
          port:
            - name: eth1
              vlan:
                mode: trunk
                trunk-tags:
                  - id: 100
                  - id: 100
        "#,
    )
    .unwrap();

    let result = desired.sanitize();

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_bridge_vlan_filter_enable_native_with_access_mode() {
    let mut desired: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            stp:
              enabled: true
          port:
            - name: eth1
              vlan:
                enable-native: true
                mode: access
        "#,
    )
    .unwrap();

    let result = desired.sanitize();

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_bridge_vlan_filter_trunk_tags_with_access_mode() {
    let mut desired: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            stp:
              enabled: true
          port:
            - name: eth1
              vlan:
                mode: access
                trunk-tags:
                  - id: 100
        "#,
    )
    .unwrap();

    let result = desired.sanitize();

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_bridge_vlan_filter_no_trunk_tags_with_trunk_mode() {
    let mut desired: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            stp:
              enabled: true
          port:
            - name: eth1
              vlan:
                mode: trunk
        "#,
    )
    .unwrap();

    let result = desired.sanitize();

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_bridge_validate_diff_group_forward_mask_and_group_fwd_mask() {
    let mut desired: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            group-forward-mask: 1
            group-fwd-mask: 2
        "#,
    )
    .unwrap();
    let result = desired.sanitize();

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e
            .msg()
            .contains("Linux bridge br0 has different group_forward_mask:"));
    }
}

#[test]
fn test_bridge_sanitize_group_forward_mask_and_group_fwd_mask() {
    let mut desired_both: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            group-forward-mask: 1
            group-fwd-mask: 1
        "#,
    )
    .unwrap();
    desired_both.sanitize().unwrap();

    let mut desired_old: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            group-forward-mask: 1
        "#,
    )
    .unwrap();
    desired_old.sanitize().unwrap();

    let mut desired_new: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            group-fwd-mask: 1
        "#,
    )
    .unwrap();
    desired_new.sanitize().unwrap();

    let expected: LinuxBridgeInterface = serde_yaml::from_str(
        r#"
        name: br0
        type: linux-bridge
        state: up
        bridge:
          options:
            group-fwd-mask: 1
        "#,
    )
    .unwrap();

    assert_eq!(desired_both, expected);
    assert_eq!(desired_old, expected);
    assert_eq!(desired_new, expected);
}
