// SPDX-License-Identifier: Apache-2.0

use crate::{
    unit_tests::testlib::new_eth_iface, BridgePortVlanMode, ErrorKind,
    EthernetConfig, EthernetDuplex, Interface, InterfaceType, Interfaces,
    MergedInterfaces, NetworkState, SrIovConfig, SrIovVfConfig,
};

#[test]
fn test_sriov_vf_mac_mix_case() {
    let mut pre_apply_cur_ifaces = Interfaces::new();
    pre_apply_cur_ifaces.push(new_eth_iface("eth1"));

    let mut cur_ifaces = Interfaces::new();
    let mut cur_iface = new_eth_iface("eth1");
    if let Interface::Ethernet(ref mut eth_iface) = cur_iface {
        let mut eth_conf = EthernetConfig::new();
        let mut sriov_conf = SrIovConfig::new();
        let mut vf_conf = SrIovVfConfig::new();
        vf_conf.id = 0;
        vf_conf.mac_address = Some("00:11:22:33:44:FF".into());
        vf_conf.iface_name = "eth1v0".to_string();
        sriov_conf.vfs = Some(vec![vf_conf]);
        sriov_conf.total_vfs = Some(1);
        eth_conf.sr_iov = Some(sriov_conf);
        eth_iface.ethernet = Some(eth_conf);
    } else {
        panic!("Should be ethernet interface");
    }
    cur_ifaces.push(new_eth_iface("eth1v0"));
    cur_ifaces.push(cur_iface);

    let mut des_ifaces = Interfaces::new();
    let mut des_iface = new_eth_iface("eth1");
    if let Interface::Ethernet(ref mut eth_iface) = des_iface {
        let mut eth_conf = EthernetConfig::new();
        let mut sriov_conf = SrIovConfig::new();
        let mut vf_conf = SrIovVfConfig::new();
        vf_conf.id = 0;
        vf_conf.mac_address = Some("00:11:22:33:44:Ff".into());
        sriov_conf.vfs = Some(vec![vf_conf]);
        eth_conf.sr_iov = Some(sriov_conf);
        eth_iface.ethernet = Some(eth_conf);
    } else {
        panic!("Should be ethernet interface");
    }
    des_ifaces.push(des_iface);

    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, pre_apply_cur_ifaces, false, false)
            .unwrap();

    merged_ifaces.verify(&cur_ifaces).unwrap();
}

#[test]
fn test_ignore_sriov_if_not_desired() {
    let mut pre_apply_cur_ifaces = Interfaces::new();
    pre_apply_cur_ifaces.push(new_eth_iface("eth1"));
    let current = serde_yaml::from_str::<Interfaces>(
        r#"---
- name: eth1
  type: ethernet
  state: up
  mtu: 1280
  ethernet:
    sr-iov:
      total-vfs: 2
      vfs:
      - id: 0
        mac-address: 02:54:00:17:12:ff
        spoof-check: true
        vlan-id: 102
        qos: 5
      - id: 1
        vlan-id: 101
        qos: 6
"#,
    )
    .unwrap();
    let desired = serde_yaml::from_str::<Interfaces>(
        r#"---
- name: eth1
  type: ethernet
  state: up
  mtu: 1280
"#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, pre_apply_cur_ifaces, false, false)
            .unwrap();

    merged_ifaces.verify(&current).unwrap();
}

fn gen_sriov_current_ifaces() -> Interfaces {
    let mut current = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: eth1
          type: ethernet
          state: up
          ethernet:
            sr-iov:
              total-vfs: 2
              vfs:
              - id: 0
              - id: 1
        - name: eth1v0
          type: ethernet
          state: up
        - name: eth1v1
          type: ethernet
          state: up
        "#,
    )
    .unwrap();
    let iface = current.kernel_ifaces.get_mut("eth1").unwrap();
    if let Interface::Ethernet(eth_iface) = iface {
        eth_iface
            .ethernet
            .as_mut()
            .unwrap()
            .sr_iov
            .as_mut()
            .unwrap()
            .vfs
            .as_mut()
            .unwrap()[0]
            .iface_name = "eth1v0".to_string();
        eth_iface
            .ethernet
            .as_mut()
            .unwrap()
            .sr_iov
            .as_mut()
            .unwrap()
            .vfs
            .as_mut()
            .unwrap()[1]
            .iface_name = "eth1v1".to_string();
    }
    current
}

#[test]
fn test_resolve_sriov_name() {
    let current = gen_sriov_current_ifaces();
    let mut desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: sriov:eth1:0
          type: ethernet
          state: up
          mtu: 1280
        - name: sriov:eth1:1
          type: ethernet
          state: up
          mtu: 1281
        "#,
    )
    .unwrap();
    desired.resolve_sriov_reference(&current).unwrap();
    let vf0_iface = desired
        .get_iface("eth1v0", InterfaceType::Ethernet)
        .unwrap();
    let vf1_iface = desired
        .get_iface("eth1v1", InterfaceType::Ethernet)
        .unwrap();
    assert_eq!(vf0_iface.base_iface().mtu, Some(1280));
    assert_eq!(vf1_iface.base_iface().mtu, Some(1281));
}

#[test]
fn test_resolve_sriov_name_duplicate() {
    let current = gen_sriov_current_ifaces();
    let mut desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: sriov:eth1:0
          type: ethernet
          state: up
          mtu: 1280
        - name: eth1v0
          type: ethernet
          state: up
          mtu: 1281
        "#,
    )
    .unwrap();
    let result = desired.resolve_sriov_reference(&current);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_failed_to_resolve_sriov_in_ovs_port_list() {
    let current = gen_sriov_current_ifaces();
    let mut desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: ovs-br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: sriov:eth1:2
            - name: sriov:eth1:1
        "#,
    )
    .unwrap();
    let result = desired.resolve_sriov_reference(&current);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_verify_sriov_name() {
    let current = gen_sriov_current_ifaces();
    let desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: sriov:eth1:0
          type: ethernet
          state: up
        "#,
    )
    .unwrap();
    let merged_ifaces =
        MergedInterfaces::new(desired, current.clone(), false, false).unwrap();

    merged_ifaces.verify(&current).unwrap();
}

#[test]
fn test_resolve_sriov_port_name_linux_bridge() {
    let current = gen_sriov_current_ifaces();
    let mut desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: br0
          type: linux-bridge
          state: up
          bridge:
            port:
            - name: sriov:eth1:1
              vlan:
                mode: access
                tag: 305
        "#,
    )
    .unwrap();
    desired.resolve_sriov_reference(&current).unwrap();
    if let Interface::LinuxBridge(br_iface) = desired
        .get_iface("br0", InterfaceType::LinuxBridge)
        .unwrap()
    {
        let port_confs =
            br_iface.bridge.as_ref().unwrap().port.as_ref().unwrap();
        assert_eq!(port_confs.len(), 1);
        assert_eq!(port_confs[0].name, "eth1v1".to_string());
        assert_eq!(
            port_confs[0].vlan.as_ref().unwrap().mode.unwrap(),
            BridgePortVlanMode::Access
        );
        assert_eq!(port_confs[0].vlan.as_ref().unwrap().tag.unwrap(), 305);
    } else {
        panic!("Failed to find expected bridge interface br0");
    }
}

#[test]
fn test_resolve_sriov_port_name_bond() {
    let current = gen_sriov_current_ifaces();
    let mut desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: bond0
          type: bond
          state: up
          link-aggregation:
            mode: balance-rr
            port:
            - sriov:eth1:1
            - sriov:eth1:0
        "#,
    )
    .unwrap();
    desired.resolve_sriov_reference(&current).unwrap();
    let bond_iface = desired.get_iface("bond0", InterfaceType::Bond).unwrap();
    let ports = bond_iface.ports().unwrap();
    assert_eq!(ports.len(), 2);
    assert_eq!(ports, vec!["eth1v1", "eth1v0"]);
}

#[test]
fn test_resolve_sriov_port_name_ovs_bridge() {
    let current = gen_sriov_current_ifaces();
    let mut desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: ovs-br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: sriov:eth1:0
            - name: sriov:eth1:1
        "#,
    )
    .unwrap();
    desired.resolve_sriov_reference(&current).unwrap();
    let br_iface = desired
        .get_iface("ovs-br0", InterfaceType::OvsBridge)
        .unwrap();
    let ports = br_iface.ports().unwrap();
    assert_eq!(ports.len(), 2);
    assert_eq!(ports, vec!["eth1v0", "eth1v1"]);
}

#[test]
fn test_resolve_sriov_port_name_ovs_bond() {
    let current = gen_sriov_current_ifaces();
    let mut desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: ovs-br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: bond1
              link-aggregation:
                mode: balance-slb
                port:
                  - name: eth2
                  - name: sriov:eth1:1
        "#,
    )
    .unwrap();
    desired.resolve_sriov_reference(&current).unwrap();
    let br_iface = desired
        .get_iface("ovs-br0", InterfaceType::OvsBridge)
        .unwrap();
    let ports = br_iface.ports().unwrap();
    assert_eq!(ports.len(), 2);
    assert_eq!(ports, vec!["eth2", "eth1v1"]);
}

#[test]
fn test_verify_sriov_port_name_linux_bridge() {
    let pre_apply_current = gen_sriov_current_ifaces();
    let desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: br0
          type: linux-bridge
          state: up
          bridge:
            port:
            - name: sriov:eth1:1
              vlan:
                mode: access
                tag: 305
        "#,
    )
    .unwrap();
    let mut current = gen_sriov_current_ifaces();
    current.push(
        serde_yaml::from_str::<Interface>(
            r#"---
            name: br0
            type: linux-bridge
            state: up
            bridge:
              port:
              - name: eth1v1
                vlan:
                  mode: access
                  tag: 305
        "#,
        )
        .unwrap(),
    );
    let merged_ifaces =
        MergedInterfaces::new(desired, pre_apply_current, false, false)
            .unwrap();

    merged_ifaces.verify(&current).unwrap();
}

#[test]
fn test_verify_sriov_port_name_bond() {
    let pre_apply_current = gen_sriov_current_ifaces();
    let desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: bond0
          type: bond
          state: up
          link-aggregation:
            mode: balance-rr
            port:
            - sriov:eth1:1
        "#,
    )
    .unwrap();
    let mut current = gen_sriov_current_ifaces();
    current.push(
        serde_yaml::from_str::<Interface>(
            r#"---
            name: bond0
            type: bond
            state: up
            link-aggregation:
              mode: balance-rr
              port:
              - eth1v1
        "#,
        )
        .unwrap(),
    );

    let merged_ifaces =
        MergedInterfaces::new(desired, pre_apply_current, false, false)
            .unwrap();

    merged_ifaces.verify(&current).unwrap();
}

#[test]
fn test_verify_sriov_port_name_ovs_bridge() {
    let pre_apply_current = gen_sriov_current_ifaces();
    let desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: ovs-br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: sriov:eth1:1
        "#,
    )
    .unwrap();
    let mut current = gen_sriov_current_ifaces();
    current.push(
        serde_yaml::from_str::<Interface>(
            r#"---
            name: ovs-br0
            type: ovs-bridge
            state: up
            bridge:
              port:
              - name: eth1v1
            "#,
        )
        .unwrap(),
    );
    let merged_ifaces =
        MergedInterfaces::new(desired, pre_apply_current, false, false)
            .unwrap();

    merged_ifaces.verify(&current).unwrap();
}

#[test]
fn test_verify_sriov_port_name_ovs_bond() {
    let pre_apply_current = gen_sriov_current_ifaces();
    let desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: ovs-br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: bond1
              link-aggregation:
                mode: balance-slb
                port:
                  - name: sriov:eth1:1
                  - name: sriov:eth1:0
        "#,
    )
    .unwrap();
    let mut current = gen_sriov_current_ifaces();
    current.push(
        serde_yaml::from_str::<Interface>(
            r#"---
            name: ovs-br0
            type: ovs-bridge
            state: up
            bridge:
              port:
              - name: bond1
                link-aggregation:
                  mode: balance-slb
                  port:
                    - name: eth1v0
                    - name: eth1v1
              "#,
        )
        .unwrap(),
    );
    let merged_ifaces =
        MergedInterfaces::new(desired, pre_apply_current, false, false)
            .unwrap();

    merged_ifaces.verify(&current).unwrap();
}

#[test]
fn test_sriov_vf_auto_fill_vf_conf() {
    let mut cur_ifaces = Interfaces::new();
    let mut cur_iface = new_eth_iface("eth1");
    if let Interface::Ethernet(ref mut eth_iface) = cur_iface {
        let mut eth_conf = EthernetConfig::new();
        let mut sriov_conf = SrIovConfig::new();
        let mut vfs = Vec::new();
        for i in 0..4 {
            let mut vf_conf = SrIovVfConfig::new();
            vf_conf.id = i;
            if i == 2 {
                vf_conf.trust = Some(true);
            }
            let vf_iface_name = format!("eth1v{i}");
            cur_ifaces.push(new_eth_iface(vf_iface_name.as_str()));
            vf_conf.iface_name = vf_iface_name;
            vfs.push(vf_conf);
        }
        sriov_conf.total_vfs = Some(4);
        sriov_conf.vfs = Some(vfs);
        eth_conf.sr_iov = Some(sriov_conf);
        eth_iface.ethernet = Some(eth_conf);
    } else {
        panic!("Should be ethernet interface");
    }
    cur_ifaces.push(cur_iface);

    let mut pre_apply_current = cur_ifaces.clone();
    for iface in pre_apply_current.kernel_ifaces.values_mut() {
        if let Interface::Ethernet(ref mut eth_iface) = iface {
            if let Some(vfs) = eth_iface
                .ethernet
                .as_mut()
                .and_then(|eth_conf| eth_conf.sr_iov.as_mut())
                .and_then(|sr_iov_conf| sr_iov_conf.vfs.as_mut())
            {
                for vf in vfs {
                    vf.trust = Some(false);
                }
            }
        }
    }

    let mut des_ifaces = Interfaces::new();
    let mut des_iface = new_eth_iface("eth1");
    if let Interface::Ethernet(ref mut eth_iface) = des_iface {
        let mut eth_conf = EthernetConfig::new();
        let mut sriov_conf = SrIovConfig::new();
        let mut vf_conf = SrIovVfConfig::new();
        vf_conf.id = 2;
        vf_conf.trust = Some(true);
        sriov_conf.vfs = Some(vec![vf_conf]);
        eth_conf.sr_iov = Some(sriov_conf);
        eth_iface.ethernet = Some(eth_conf);
    } else {
        panic!("Should be ethernet interface");
    }
    des_ifaces.push(des_iface);

    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, pre_apply_current, false, false)
            .unwrap();

    merged_ifaces.verify(&cur_ifaces).unwrap();

    let iface = merged_ifaces
        .get_iface("eth1", InterfaceType::Ethernet)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(
        serde_yaml::to_string(iface).unwrap(),
        serde_yaml::to_string(
            cur_ifaces
                .get_iface("eth1", InterfaceType::Ethernet)
                .unwrap()
        )
        .unwrap()
    );
}

#[test]
fn test_sriov_enable_and_use_in_single_yaml() {
    let desired = serde_yaml::from_str::<NetworkState>(
        r#"---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          ethernet:
            speed: 10000
            duplex: full
            auto-negotiation: false
            sr-iov:
              total-vfs: 2
        - name: eth1v0
          type: ethernet
          state: up
        - name: eth1v1
          type: ethernet
          state: up
        "#,
    )
    .unwrap();

    let pf_state = desired.get_sriov_pf_conf_state().unwrap();

    if let Interface::Ethernet(pf_iface) =
        pf_state.interfaces.kernel_ifaces.get("eth1").unwrap()
    {
        let eth_conf = pf_iface.ethernet.as_ref().unwrap();
        assert_eq!(eth_conf.auto_neg, Some(false));
        assert_eq!(eth_conf.speed, Some(10000));
        assert_eq!(eth_conf.duplex, Some(EthernetDuplex::Full));
        let sr_iov_conf = eth_conf.sr_iov.as_ref().unwrap();
        assert_eq!(sr_iov_conf.total_vfs, Some(2));
    } else {
        panic!("Expecting Ethernet interface, got {:?}", pf_state);
    }
}

#[test]
fn test_sriov_has_vf_count_change_and_missing_eth() {
    let desired = serde_yaml::from_str::<NetworkState>(
        r#"---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          ethernet:
            speed: 10000
            duplex: full
            auto-negotiation: false
            sr-iov:
              total-vfs: 2
        - name: eth1v0
          type: ethernet
          state: up
        - name: eth1v1
          type: ethernet
          state: up
        "#,
    )
    .unwrap();
    let current = serde_yaml::from_str::<NetworkState>(
        r#"---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          ethernet:
            speed: 10000
            duplex: full
            auto-negotiation: false
            sr-iov:
              total-vfs: 0
        "#,
    )
    .unwrap();

    assert!(desired.has_vf_count_change_and_missing_eth(&current));
}

#[test]
fn test_sriov_has_vf_count_change_and_missing_eth_pf_none() {
    let desired = serde_yaml::from_str::<NetworkState>(
        r#"---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          ethernet:
            speed: 10000
            duplex: full
            auto-negotiation: false
            sr-iov:
              total-vfs: 2
        - name: eth1v0
          state: up
        - name: eth1v1
          state: up
        "#,
    )
    .unwrap();
    let current = serde_yaml::from_str::<NetworkState>(
        r#"---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
        "#,
    )
    .unwrap();

    assert!(desired.has_vf_count_change_and_missing_eth(&current));
}

#[test]
fn test_sriov_vf_revert_to_default() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: eth1
          type: ethernet
          state: up
          ethernet:
            sr-iov:
              total-vfs: 2
              vfs: []
        "#,
    )
    .unwrap();

    let current = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: eth1
          type: ethernet
          state: up
          ethernet:
            sr-iov:
              total-vfs: 2
              vfs:
                - id: 0
                  mac-address: D4:eE:00:25:42:5a
                  max-tx-rate: 1000
                  min-tx-rate: 1
                  spoof-check: true
                  trust: true
                - id: 1
                  trust: true
                  spoof-check: true
                  min-tx-rate: 1
                  max-tx-rate: 1000
                  mac-address: d4:Ee:01:25:42:5A
        "#,
    )
    .unwrap();

    let mut merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let iface = merged_ifaces
        .kernel_ifaces
        .get("eth1")
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    if let Interface::Ethernet(iface) = iface {
        assert_eq!(
            iface
                .ethernet
                .as_ref()
                .and_then(|e| e.sr_iov.as_ref())
                .and_then(|s| s.vfs.as_ref()),
            Some(&Vec::new())
        );
    } else {
        panic!("Expecting a Ethernet interface, but got {:?}", iface);
    }

    let verify_iface = merged_ifaces
        .kernel_ifaces
        .get_mut("eth1")
        .unwrap()
        .for_verify
        .as_mut()
        .unwrap();

    verify_iface.sanitize_desired_for_verify();

    if let Interface::Ethernet(iface) = verify_iface {
        assert_eq!(
            iface
                .ethernet
                .as_ref()
                .and_then(|e| e.sr_iov.as_ref())
                .and_then(|s| s.vfs.as_ref()),
            None
        );
    } else {
        panic!("Expecting a Ethernet interface, but got {:?}", verify_iface);
    }
}

#[test]
fn test_has_vf_change_with_unknown_iface_type() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: eth1
          state: up
          ethernet:
            sr-iov:
              total-vfs: 2
        "#,
    )
    .unwrap();

    let current = serde_yaml::from_str::<Interfaces>(
        r#"---
        - name: eth1
          type: ethernet
          state: up
          ethernet:
            sr-iov:
              total-vfs: 1
        "#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    assert!(merged_ifaces.has_vf_count_change());
}
