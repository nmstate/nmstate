// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, Interface, InterfaceType, Interfaces, MergedInterface,
    MergedInterfaces, NetworkState, OvsBridgeBondMode, OvsBridgeInterface,
    OvsInterface,
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

    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        cur_ifaces,
        Default::default(),
        false,
    )
    .unwrap();

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

    assert_eq!(br0_iface.ports(), Some(vec!["br0", "eth2"]));

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
    - name: br0
- name: br0
  type: ovs-interface
  state: up
  controller: br0
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

    let merged_iface = MergedInterfaces::new(
        des_ifaces,
        pre_apply_cur_ifaces,
        Default::default(),
        false,
    )
    .unwrap();

    merged_iface.verify(&cur_ifaces).unwrap();
}

#[test]
fn test_ovs_local_port_respects_ignore_in_desired() {
    let current: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  bridge:
    port:
    - name: eth1
    - name: br0
- name: br0
  type: ovs-interface
  state: up
  controller: br0
- name: eth1
  type: ethernet
  controller: br0
",
    )
    .unwrap();

    let desired: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-interface
  state: ignore
- name: br0
  type: ovs-bridge
  bridge:
    port:
    - name: eth1
",
    )
    .unwrap();

    let merged = MergedInterfaces::new(
        desired,
        current.clone(),
        Default::default(),
        false,
    )
    .unwrap();

    assert_eq!(
        merged.ignored_ifaces,
        vec![("br0".to_string(), InterfaceType::OvsInterface)]
    );
    assert!(
        merged
            .get_iface("br0", InterfaceType::OvsInterface)
            .is_none()
    );
    let bridge = merged.get_iface("br0", InterfaceType::OvsBridge).unwrap();
    for iface in [
        &bridge.merged,
        bridge.desired.as_ref().unwrap(),
        bridge.for_apply.as_ref().unwrap(),
        bridge.for_verify.as_ref().unwrap(),
    ] {
        assert_eq!(iface.ports(), Some(vec!["eth1"]));
    }
    merged.verify(&current).unwrap();
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
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

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
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

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
fn test_ovs_local_port_preserves_ports_on_partial_update() {
    let current: Interfaces = serde_yaml::from_str(
        r#"
- name: br0
  type: ovs-bridge
  bridge:
    port:
    - name: eth1
      vlan:
        mode: access
        tag: 100
      ovs-db:
        other_config:
          stp-path-cost: "2"
    - name: bond0
      link-aggregation:
        mode: active-backup
        port:
        - name: eth2
        - name: eth3
- name: eth1
  type: ethernet
  controller: br0
- name: eth2
  type: ethernet
  controller: br0
- name: eth3
  type: ethernet
  controller: br0
"#,
    )
    .unwrap();
    let Interface::OvsBridge(current_bridge) =
        current.get_iface("br0", InterfaceType::OvsBridge).unwrap()
    else {
        panic!("Expected an OVS bridge");
    };

    for desired in [
        r"
- name: br0
  type: ovs-bridge
  bridge:
    options:
      stp: true
",
        r"
- name: br0
  type: ovs-bridge
",
    ] {
        let merged = MergedInterfaces::new(
            serde_yaml::from_str(desired).unwrap(),
            current.clone(),
            Default::default(),
            false,
        )
        .unwrap();

        for port_name in ["eth1", "eth2", "eth3"] {
            let port = merged
                .get_iface(port_name, InterfaceType::Ethernet)
                .unwrap();
            assert_eq!(
                port.merged.base_iface().controller.as_deref(),
                Some("br0")
            );
            assert!(port.for_apply.is_none());
        }

        let bridge = merged.get_iface("br0", InterfaceType::OvsBridge).unwrap();
        for iface in [
            &bridge.merged,
            bridge.desired.as_ref().unwrap(),
            bridge.for_apply.as_ref().unwrap(),
        ] {
            let Interface::OvsBridge(iface) = iface else {
                panic!("Expected an OVS bridge");
            };
            let ports = iface.port_confs();
            assert_eq!(ports.len(), 3);
            assert!(ports.iter().any(|p| p.name == "br0"));
            for current_port in current_bridge.port_confs() {
                assert_eq!(
                    ports.iter().find(|p| p.name == current_port.name).copied(),
                    Some(current_port)
                );
            }
        }
        assert!(bridge.for_verify.as_ref().unwrap().ports().is_none());

        let local_port = merged
            .get_iface("br0", InterfaceType::OvsInterface)
            .unwrap()
            .for_apply
            .as_ref()
            .unwrap();
        assert_eq!(local_port.base_iface().controller.as_deref(), Some("br0"));
    }
}

#[test]
fn test_ovs_local_port_honors_explicit_port_list() {
    let current: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  bridge:
    port:
    - name: eth1
    - name: eth2
- name: eth1
  type: ethernet
  controller: br0
- name: eth2
  type: ethernet
  controller: br0
",
    )
    .unwrap();

    for (desired, expected_ports) in [
        (
            r"
- name: br0
  type: ovs-bridge
  bridge:
    port: []
",
            vec!["br0"],
        ),
        (
            r"
- name: br0
  type: ovs-bridge
  bridge:
    port:
    - name: eth1
",
            vec!["br0", "eth1"],
        ),
    ] {
        let merged = MergedInterfaces::new(
            serde_yaml::from_str(desired).unwrap(),
            current.clone(),
            Default::default(),
            false,
        )
        .unwrap();
        let bridge = merged
            .get_iface("br0", InterfaceType::OvsBridge)
            .unwrap()
            .for_apply
            .as_ref()
            .unwrap();
        assert_eq!(bridge.ports(), Some(expected_ports.clone()));

        for port_name in ["eth1", "eth2"] {
            let port = merged
                .get_iface(port_name, InterfaceType::Ethernet)
                .unwrap();
            if expected_ports.contains(&port_name) {
                assert!(port.for_apply.is_none());
            } else {
                assert_eq!(
                    port.for_apply
                        .as_ref()
                        .unwrap()
                        .base_iface()
                        .controller
                        .as_deref(),
                    Some("")
                );
            }
        }
    }
}

// Ports can be attached using the `controller` property, without being in
// the port list. They must be kept when the omitted port list is filled in.
#[test]
fn test_ovs_local_port_with_ports_attached_via_controller_prop() {
    let existing_bridge: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
- name: eth1
  type: ethernet
  state: up
  controller: br0
- name: eth2
  type: ethernet
  state: up
- name: eth3
  type: ethernet
  state: up
",
    )
    .unwrap();
    let no_bridge: Interfaces = serde_yaml::from_str(
        r"
- name: eth2
  type: ethernet
  state: up
- name: eth3
  type: ethernet
  state: up
",
    )
    .unwrap();
    let desired: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    options:
      stp: true
- name: eth2
  type: ethernet
  state: up
  controller: br0
- name: eth3
  type: ethernet
  state: up
",
    )
    .unwrap();

    for (current, expected_ports) in [
        (existing_bridge, vec!["br0", "eth1", "eth2"]),
        (no_bridge, vec!["br0", "eth2"]),
    ] {
        let merged = MergedInterfaces::new(
            desired.clone(),
            current,
            Default::default(),
            false,
        )
        .unwrap();

        let bridge = merged.get_iface("br0", InterfaceType::OvsBridge).unwrap();
        for iface in [
            &bridge.merged,
            bridge.desired.as_ref().unwrap(),
            bridge.for_apply.as_ref().unwrap(),
        ] {
            let mut ports = iface.ports().unwrap();
            ports.sort_unstable();
            assert_eq!(ports, expected_ports);
        }
        assert!(bridge.for_verify.as_ref().unwrap().ports().is_none());

        for (iface_name, iface_type, controller) in [
            ("br0", InterfaceType::OvsInterface, Some("br0")),
            ("eth2", InterfaceType::Ethernet, Some("br0")),
            ("eth3", InterfaceType::Ethernet, None),
        ] {
            assert_eq!(
                merged
                    .get_iface(iface_name, iface_type)
                    .unwrap()
                    .for_apply
                    .as_ref()
                    .unwrap()
                    .base_iface()
                    .controller
                    .as_deref(),
                controller
            );
        }
    }
}

#[test]
fn test_ovs_local_port_name_is_not_resolved_as_profile() {
    let current: Interfaces = serde_yaml::from_str(
        r"
- name: eth1
  type: ethernet
- name: eth2
  type: ethernet
",
    )
    .unwrap();
    let desired: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  bridge:
    port:
    - name: eth1
",
    )
    .unwrap();

    for profile_holders in [vec!["eth1"], vec!["eth2"], vec!["eth1", "eth2"]] {
        let mut current = current.clone();
        for iface_name in profile_holders {
            current
                .get_iface_mut(iface_name, InterfaceType::Ethernet)
                .unwrap()
                .base_iface_mut()
                .profile_name = Some("br0".to_string());
        }
        let merged = MergedInterfaces::new(
            desired.clone(),
            current,
            Default::default(),
            false,
        )
        .unwrap();

        let bridge = merged.get_iface("br0", InterfaceType::OvsBridge).unwrap();
        for iface in [
            &bridge.merged,
            bridge.desired.as_ref().unwrap(),
            bridge.for_apply.as_ref().unwrap(),
            bridge.for_verify.as_ref().unwrap(),
        ] {
            let mut ports = iface.ports().unwrap();
            ports.sort_unstable();
            assert_eq!(ports, vec!["br0", "eth1"]);
        }
        let local_port = merged
            .get_iface("br0", InterfaceType::OvsInterface)
            .unwrap()
            .for_apply
            .as_ref()
            .unwrap();
        assert_eq!(local_port.iface_type(), InterfaceType::OvsInterface);
        assert_eq!(local_port.base_iface().controller.as_deref(), Some("br0"));
        assert_eq!(
            merged
                .get_iface("eth1", InterfaceType::Ethernet)
                .unwrap()
                .merged
                .base_iface()
                .controller
                .as_deref(),
            Some("br0")
        );
        assert!(
            merged
                .get_iface("eth2", InterfaceType::Ethernet)
                .unwrap()
                .for_apply
                .is_none()
        );
    }
}

fn verify_local_port_referenced_by_other_name(
    local_port_name_conf: &str,
    port_ref: &str,
) {
    let current: Interfaces = serde_yaml::from_str(&format!(
        r"
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: br0
- name: br0
  type: ovs-interface
  state: up
  controller: br0
  {local_port_name_conf}
- name: eth1
  type: ethernet
  state: up
  controller: br0
"
    ))
    .unwrap();
    let desired: Interfaces = serde_yaml::from_str(&format!(
        r"
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: {port_ref}
"
    ))
    .unwrap();

    let merged =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    let bridge = merged.get_iface("br0", InterfaceType::OvsBridge).unwrap();
    for iface in [
        &bridge.merged,
        bridge.for_apply.as_ref().unwrap(),
        bridge.for_verify.as_ref().unwrap(),
    ] {
        let mut ports = iface.ports().unwrap();
        ports.sort_unstable();
        assert_eq!(ports, vec!["br0", "eth1"]);
    }
}

#[test]
fn test_ovs_local_port_referenced_by_profile_name() {
    verify_local_port_referenced_by_other_name(
        "profile-name: br0-if",
        "br0-if",
    );
}

#[test]
fn test_ovs_local_port_referenced_by_alt_name() {
    verify_local_port_referenced_by_other_name(
        "alt-names:\n  - name: br0-alt",
        "br0-alt",
    );
}

#[test]
fn test_ovs_local_port_absent_or_down_is_honored() {
    let current: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: br0
- name: br0
  type: ovs-interface
  state: up
  controller: br0
- name: eth1
  type: ethernet
  state: up
  controller: br0
",
    )
    .unwrap();

    // Memory-only mode turns absent into down
    for state in ["absent", "down"] {
        for memory_only in [false, true] {
            let desired: Interfaces = serde_yaml::from_str(&format!(
                r"
- name: br0
  type: ovs-interface
  state: {state}
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
"
            ))
            .unwrap();

            let merged = MergedInterfaces::new(
                desired,
                current.clone(),
                Default::default(),
                memory_only,
            )
            .unwrap();

            let bridge =
                merged.get_iface("br0", InterfaceType::OvsBridge).unwrap();
            for iface in [
                bridge.for_apply.as_ref().unwrap(),
                bridge.for_verify.as_ref().unwrap(),
            ] {
                assert_eq!(iface.ports(), Some(vec!["eth1"]));
            }
            // A detached OVS interface cannot live without controller, so it
            // is removed even when marked as down
            let local_port = merged
                .get_iface("br0", InterfaceType::OvsInterface)
                .unwrap()
                .for_apply
                .as_ref()
                .unwrap();
            assert!(local_port.is_absent());
        }
    }
}

#[test]
fn test_ovs_local_port_absent_or_down_without_other_ports() {
    let only_local_port: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: br0
- name: br0
  type: ovs-interface
  state: up
  controller: br0
",
    )
    .unwrap();

    for (current, bridge_conf) in [
        (Interfaces::new(), ""),
        (Interfaces::new(), "bridge:\n    port: []"),
        (only_local_port, "bridge:\n    port: []"),
    ] {
        for state in ["absent", "down"] {
            for memory_only in [false, true] {
                let desired: Interfaces = serde_yaml::from_str(&format!(
                    r"
- name: br0
  type: ovs-interface
  state: {state}
- name: br0
  type: ovs-bridge
  state: up
  {bridge_conf}
"
                ))
                .unwrap();

                let e = MergedInterfaces::new(
                    desired,
                    current.clone(),
                    Default::default(),
                    memory_only,
                )
                .unwrap_err();

                assert_eq!(e.kind(), ErrorKind::InvalidArgument);
                assert!(e.msg().contains("has no ports"));
            }
        }
    }
}

#[test]
fn test_ovs_local_port_name_attached_to_other_bridge() {
    let current: Interfaces = serde_yaml::from_str(
        r"
- name: eth1
  type: ethernet
  state: up
",
    )
    .unwrap();
    let desired: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
- name: br1
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: br0
- name: br0
  type: ovs-interface
  state: up
  controller: br1
",
    )
    .unwrap();

    let merged =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    assert_eq!(
        merged
            .get_iface("br0", InterfaceType::OvsBridge)
            .unwrap()
            .for_apply
            .as_ref()
            .unwrap()
            .ports(),
        Some(vec!["eth1"])
    );
    assert_eq!(
        merged
            .get_iface("br0", InterfaceType::OvsInterface)
            .unwrap()
            .for_apply
            .as_ref()
            .unwrap()
            .base_iface()
            .controller
            .as_deref(),
        Some("br1")
    );
}

// Same as above, but the OVS interface with the bridge name does not exist
// and is not defined in the desired state. It will be created as port of
// the other bridge.
#[test]
fn test_ovs_local_port_name_listed_as_port_of_other_bridge() {
    let current: Interfaces = serde_yaml::from_str(
        r"
- name: eth1
  type: ethernet
  state: up
",
    )
    .unwrap();
    let desired: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
- name: br1
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: br0
",
    )
    .unwrap();

    let merged =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    for (br_name, expected_ports) in
        [("br0", vec!["eth1"]), ("br1", vec!["br0", "br1"])]
    {
        assert_eq!(
            merged
                .get_iface(br_name, InterfaceType::OvsBridge)
                .unwrap()
                .for_apply
                .as_ref()
                .unwrap()
                .ports(),
            Some(expected_ports)
        );
    }
    for (iface_name, controller) in [("br0", "br1"), ("br1", "br1")] {
        assert_eq!(
            merged
                .get_iface(iface_name, InterfaceType::OvsInterface)
                .unwrap()
                .for_apply
                .as_ref()
                .unwrap()
                .base_iface()
                .controller
                .as_deref(),
            Some(controller)
        );
    }
}

#[test]
fn test_ovs_local_port_name_detached() {
    let current: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: br0
- name: br0
  type: ovs-interface
  state: up
  controller: br0
- name: eth1
  type: ethernet
  state: up
  controller: br0
",
    )
    .unwrap();
    let desired = |state: &str| -> Interfaces {
        serde_yaml::from_str(&format!(
            r#"
- name: br0
  type: ovs-interface
  state: {state}
  controller: ""
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
"#
        ))
        .unwrap()
    };

    // An OVS interface cannot be up without a controller. This is the error
    // reported when the bridge does not get the local port added.
    let e = MergedInterfaces::new(
        desired("up"),
        current.clone(),
        Default::default(),
        false,
    )
    .unwrap_err();
    assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    assert!(e.msg().contains("cannot live without controller"));

    let merged = MergedInterfaces::new(
        desired("down"),
        current,
        Default::default(),
        false,
    )
    .unwrap();

    assert_eq!(
        merged
            .get_iface("br0", InterfaceType::OvsBridge)
            .unwrap()
            .for_apply
            .as_ref()
            .unwrap()
            .ports(),
        Some(vec!["eth1"])
    );
    assert!(
        merged
            .get_iface("br0", InterfaceType::OvsInterface)
            .unwrap()
            .for_apply
            .as_ref()
            .unwrap()
            .is_absent()
    );
}

#[test]
fn test_ovs_local_port_skipped_for_long_bridge_name() {
    let current: Interfaces = serde_yaml::from_str(
        r"
- name: eth1
  type: ethernet
  state: up
",
    )
    .unwrap();
    // The local port is a kernel interface and its name is limited to 15
    // characters
    let desired: Interfaces = serde_yaml::from_str(
        r"
- name: br-provider-vln1
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
",
    )
    .unwrap();

    let merged =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    let bridge = merged
        .get_iface("br-provider-vln1", InterfaceType::OvsBridge)
        .unwrap();
    for iface in [
        &bridge.merged,
        bridge.for_apply.as_ref().unwrap(),
        bridge.for_verify.as_ref().unwrap(),
    ] {
        assert_eq!(iface.ports(), Some(vec!["eth1"]));
    }
    assert!(
        merged
            .get_iface("br-provider-vln1", InterfaceType::OvsInterface)
            .is_none()
    );
}

#[test]
fn test_ovs_local_port_long_bridge_name_without_ports() {
    for bridge_conf in ["", "bridge:\n    port: []"] {
        let desired: Interfaces = serde_yaml::from_str(&format!(
            r"
- name: br-provider-vln1
  type: ovs-bridge
  state: up
  {bridge_conf}
"
        ))
        .unwrap();

        let e = MergedInterfaces::new(
            desired,
            Interfaces::new(),
            Default::default(),
            false,
        )
        .unwrap_err();

        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("has no ports"));
    }
}

#[test]
fn test_ovs_local_port_max_length_bridge_name() {
    let current: Interfaces = serde_yaml::from_str(
        r"
- name: eth1
  type: ethernet
  state: up
",
    )
    .unwrap();
    let desired: Interfaces = serde_yaml::from_str(
        r"
- name: br-provider-vln
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
",
    )
    .unwrap();

    let merged =
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap();

    let bridge = merged
        .get_iface("br-provider-vln", InterfaceType::OvsBridge)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    assert_eq!(bridge.ports(), Some(vec!["br-provider-vln", "eth1"]));
    assert!(
        merged
            .get_iface("br-provider-vln", InterfaceType::OvsInterface)
            .is_some()
    );
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
fn test_ovs_bridge_vlan_native_modes() {
    for mode in ["native-tagged", "native-untagged"] {
        let mut desired: OvsBridgeInterface = serde_yaml::from_str(&format!(
            r"
            name: br0
            type: ovs-bridge
            state: up
            bridge:
              port:
                - name: eth1
                  vlan:
                    mode: {mode}
                    tag: 100
                    enable-native: true
                    trunk-tags:
                      - id: 200
                      - id: 300
            "
        ))
        .unwrap();

        desired.sanitize(true).unwrap();
        let port = &desired.bridge.unwrap().ports.unwrap()[0];
        let vlan = port.vlan.as_ref().unwrap();
        assert_eq!(vlan.mode.unwrap().to_string(), mode);
        assert_eq!(vlan.tag, Some(100));
        assert_eq!(vlan.enable_native, Some(true));
    }
}

#[test]
fn test_ovs_bridge_vlan_native_mode_without_explicit_enable_native() {
    let mut desired: OvsBridgeInterface = serde_yaml::from_str(
        r"
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
            - name: eth1
              vlan:
                mode: native-untagged
                tag: 100
        ",
    )
    .unwrap();

    desired.sanitize(true).unwrap();
}

#[test]
fn test_ovs_bridge_vlan_native_mode_rejects_disabled_native() {
    let mut desired: OvsBridgeInterface = serde_yaml::from_str(
        r"
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
            - name: eth1
              vlan:
                mode: native-tagged
                tag: 100
                enable-native: false
        ",
    )
    .unwrap();

    let result = desired.sanitize(true);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("enable-native"));
    }
}

#[test]
fn test_ovs_bridge_vlan_native_mode_requires_tag() {
    for yaml in [
        r"
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
            - name: eth1
              vlan:
                mode: native-untagged
                enable-native: true
        ",
        r"
        name: br0
        type: ovs-bridge
        state: up
        bridge:
          port:
            - name: eth1
              vlan:
                mode: native-tagged
                tag: 0
                enable-native: true
        ",
    ] {
        let mut desired: OvsBridgeInterface =
            serde_yaml::from_str(yaml).unwrap();
        let result = desired.sanitize(true);
        assert!(result.is_err());
        if let Err(e) = result {
            assert_eq!(e.kind(), ErrorKind::InvalidArgument);
            assert!(e.msg().contains("tag"));
        }
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

    MergedInterfaces::new(des_ifaces, cur_ifaces, Default::default(), false)
        .unwrap();
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

    MergedInterfaces::new(des_ifaces, cur_ifaces, Default::default(), false)
        .unwrap();
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
    - name: br0
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
    - name: br1
- name: patch1
  type: ovs-interface
  state: up
  controller: br1
  lldp:
    enabled: false
  patch:
    peer: patch0
- name: br0
  type: ovs-interface
  state: up
  controller: br0
- name: br1
  type: ovs-interface
  state: up
  controller: br1
",
    )
    .unwrap();

    let merged_iface = MergedInterfaces::new(
        des_ifaces,
        pre_apply_cur_ifaces,
        Default::default(),
        false,
    )
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

    let merged_iface = MergedInterfaces::new(
        des_ifaces,
        pre_apply_cur_ifaces,
        Default::default(),
        false,
    )
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
fn test_deny_unknown_field_in_ovs_bond() {
    let result = serde_yaml::from_str::<OvsBridgeInterface>(
        r"
        name: br0
        type: ovs-bridge
        state: up
        mac-address: 05:04:03:02:01:00
        bridge:
          port:
          - name: bond1
            link-aggregation:
              mode: active-backup
              bond-downdelay: 100
              bond-updelay: 101
              invalid: foo
              ports:
              - name: eth1
              - name: eth2
        ",
    );

    assert!(result.is_err());
}

#[test]
fn test_ovs_bond_alias() {
    let iface: OvsBridgeInterface = serde_yaml::from_str(
        r"---
name: br0
type: ovs-bridge
state: up
bridge:
  ports:
  - name: eth1
  - name: bond1
    bond:
      mode: balance-slb
      ports:
        - name: eth2
",
    )
    .unwrap();

    let br_conf = iface.bridge.as_ref().unwrap();
    let port_conf = &br_conf.ports.as_ref().unwrap()[1];
    let bond_conf = port_conf.bond.as_ref().unwrap();

    assert_eq!(iface.ports(), Some(vec!["eth1", "eth2"]));

    assert_eq!(bond_conf.mode, Some(OvsBridgeBondMode::BalanceSlb));
}

#[test]
fn test_ovs_bridge_ignore_extra_ports_for_verify() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
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
            allow-extra-ports: true
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
        - name: eth3
          type: ethernet
          state: up
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: eth1
            - name: eth2
            - name: eth3
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
        - name: eth3
          type: ethernet
          state: up
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: eth1
            - name: eth2
            - name: eth3
            - name: br0
        - name: br0
          type: ovs-interface
          state: up
          controller: br0
        ",
    )
    .unwrap();
    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        pre_apply_cur_ifaces,
        Default::default(),
        false,
    )
    .unwrap();

    merged_ifaces.verify(&cur_ifaces).unwrap();
}

#[test]
fn test_ovs_bridge_ignore_extra_ports_for_apply() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
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
            allow-extra-ports: true
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
        - name: eth3
          type: ethernet
          state: up
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: eth1
            - name: eth2
            - name: eth3
        ",
    )
    .unwrap();
    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        pre_apply_cur_ifaces,
        Default::default(),
        false,
    )
    .unwrap();

    let for_apply_bridge = merged_ifaces
        .get_iface("br0", InterfaceType::OvsBridge)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    let for_apply_eth3 = merged_ifaces
        .get_iface("eth3", InterfaceType::Ethernet)
        .unwrap()
        .for_apply
        .as_ref();

    assert_eq!(for_apply_bridge.ports(), Some(vec!["br0", "eth1", "eth2"]));
    assert_eq!(for_apply_eth3, None);
}

#[test]
fn test_ovs_local_port_unchanged_with_allow_extra_ports() {
    let current: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  bridge:
    port:
    - name: br0
    - name: eth1
    - name: eth2
- name: br0
  type: ovs-interface
  controller: br0
- name: eth1
  type: ethernet
  controller: br0
- name: eth2
  type: ethernet
  controller: br0
",
    )
    .unwrap();
    let desired: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  bridge:
    allow-extra-ports: true
    port:
    - name: eth1
",
    )
    .unwrap();

    let merged = MergedInterfaces::new(
        desired,
        current.clone(),
        Default::default(),
        false,
    )
    .unwrap();

    let bridge = merged
        .get_iface("br0", InterfaceType::OvsBridge)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    assert_eq!(bridge.ports(), Some(vec!["br0", "eth1"]));
    for (port_name, port_type) in [
        ("br0", InterfaceType::OvsInterface),
        ("eth1", InterfaceType::Ethernet),
        ("eth2", InterfaceType::Ethernet),
    ] {
        assert!(
            merged
                .get_iface(port_name, port_type)
                .unwrap()
                .for_apply
                .is_none(),
            "{port_name} should not be changed"
        );
    }

    merged.verify(&current).unwrap();
}

#[test]
#[cfg(feature = "gen_conf")]
fn test_ovs_linux_bond_port_db_gen_conf() {
    let state: crate::NetworkState = serde_yaml::from_str(
        r#"
interfaces:
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: bond0
      ovs-db:
        other_config:
          stp-path-cost: "2"
- name: bond0
  type: bond
  state: up
  link-aggregation:
    mode: active-backup
    port: [eth1]
"#,
    )
    .unwrap();
    let configs = state.gen_conf().unwrap();
    let configs = &configs["NetworkManager"];
    let port = configs
        .iter()
        .find(|(_, c)| c.contains("type=ovs-port\n"))
        .unwrap();
    assert!(port.1.contains("[ovs-other-config]\n"));
    assert!(port.1.contains("data.stp-path-cost=2\n"));
    let bond = configs
        .iter()
        .find(|(_, c)| c.contains("type=bond\n"))
        .unwrap();
    assert!(!bond.1.contains("[ovs-other-config]"));
}

#[test]
fn test_ovs_bond_port_db_normalization() {
    let mut iface: OvsBridgeInterface = serde_yaml::from_str(
        r#"
name: br0
type: ovs-bridge
"#,
    )
    .unwrap();
    let port: crate::OvsBridgePortConfig = serde_yaml::from_str(
        r#"
name: bond0
ovs-db:
  other_config:
    stp-path-cost: "2"
link-aggregation:
  mode: active-backup
  port:
  - name: eth1
  - name: eth2
"#,
    )
    .unwrap();
    let ovsdb = port.ovsdb.clone();
    iface.bridge = Some(crate::OvsBridgeConfig {
        ports: Some(vec![port.clone()]),
        ..Default::default()
    });
    iface.sanitize(true).unwrap();
    let normalized = &iface.bridge.as_ref().unwrap().ports.as_ref().unwrap()[0];
    assert!(normalized.ovsdb.is_none());
    assert_eq!(normalized.bond.as_ref().unwrap().ovsdb, ovsdb);

    let mut conflicting = port;
    conflicting.bond.as_mut().unwrap().ovsdb = Some(Default::default());
    iface.bridge.as_mut().unwrap().ports = Some(vec![conflicting]);
    assert_eq!(
        iface.sanitize(true).unwrap_err().kind(),
        ErrorKind::InvalidArgument
    );
}

#[test]
fn test_ovs_port_db_verify_clear() {
    let desired: Interfaces = serde_yaml::from_str(
        r"
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: bond0
      ovs-db:
        other_config: {}
- name: bond0
  type: bond
  state: up
",
    )
    .unwrap();
    let mut current = desired.clone();
    if let Some(Interface::OvsBridge(iface)) =
        current.get_iface_mut("br0", InterfaceType::OvsBridge)
    {
        iface.bridge.as_mut().unwrap().ports.as_mut().unwrap()[0].ovsdb = None;
    }
    let merged = MergedInterfaces::new(
        desired,
        current.clone(),
        Default::default(),
        false,
    )
    .unwrap();
    // The local port br0 is created during the apply
    current.push(
        serde_yaml::from_str::<Interface>(
            r"
name: br0
type: ovs-interface
state: up
controller: br0
",
        )
        .unwrap(),
    );
    if let Some(Interface::OvsBridge(iface)) =
        current.get_iface_mut("br0", InterfaceType::OvsBridge)
    {
        iface.bridge.as_mut().unwrap().ports.as_mut().unwrap().push(
            crate::OvsBridgePortConfig {
                name: "br0".to_string(),
                ..Default::default()
            },
        );
    }
    merged.verify(&current).unwrap();
}

// The local port is added to the desired state automatically, so gen_diff()
// reports it even when desired and current states are identical. This is
// intended: the diff reflects what nmstate is going to apply, and it is also
// used for the output of policies and `nmstatectl apply`.
#[test]
fn test_ovs_local_port_in_gen_diff_of_identical_states() {
    let state: NetworkState = serde_yaml::from_str(
        r"
interfaces:
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
- name: eth1
  type: ethernet
  state: up
  controller: br0
",
    )
    .unwrap();

    let diff = state.gen_diff(&state).unwrap();

    assert!(!diff.interfaces.is_empty());
    let bridge = diff
        .interfaces
        .get_iface("br0", InterfaceType::OvsBridge)
        .unwrap();
    let mut ports = bridge.ports().unwrap();
    ports.sort_unstable();
    assert_eq!(ports, vec!["br0", "eth1"]);
    let local_port = diff
        .interfaces
        .get_iface("br0", InterfaceType::OvsInterface)
        .unwrap();
    assert!(local_port.is_up());
    assert_eq!(local_port.base_iface().controller.as_deref(), Some("br0"));
    assert!(
        diff.interfaces
            .get_iface("eth1", InterfaceType::Ethernet)
            .is_none()
    );
}
