use crate::{
    unit_tests::testlib::new_eth_iface, BridgePortVlanMode, ErrorKind,
    EthernetConfig, Interface, InterfaceType, Interfaces, SrIovConfig,
    SrIovVfConfig,
};

#[test]
fn test_sriov_vf_mac_mix_case() {
    let mut cur_ifaces = Interfaces::new();
    let mut cur_iface = new_eth_iface("eth1");
    if let Interface::Ethernet(ref mut eth_iface) = cur_iface {
        let mut eth_conf = EthernetConfig::new();
        let mut sriov_conf = SrIovConfig::new();
        let mut vf_conf = SrIovVfConfig::new();
        vf_conf.id = 0;
        vf_conf.mac_address = Some("00:11:22:33:44:FF".into());
        sriov_conf.vfs = Some(vec![vf_conf]);
        eth_conf.sr_iov = Some(sriov_conf);
        eth_iface.ethernet = Some(eth_conf);
    } else {
        panic!("Should be ethernet interface");
    }
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

    des_ifaces.verify(&Interfaces::new(), &cur_ifaces).unwrap();
}

#[test]
fn test_ignore_sriov_if_not_desired() {
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

    desired.verify(&Interfaces::new(), &current).unwrap();
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
    desired.verify(&current, &current).unwrap();
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

    desired.verify(&pre_apply_current, &current).unwrap();
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

    desired.verify(&pre_apply_current, &current).unwrap();
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
    desired.verify(&pre_apply_current, &current).unwrap();
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
                  - name: eth2
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
              - name: bond1
                link-aggregation:
                  mode: balance-slb
                  port:
                    - name: eth1v1
                    - name: eth2
              "#,
        )
        .unwrap(),
    );
    desired.verify(&pre_apply_current, &current).unwrap();
}
