// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, EthernetInterface, InterfaceIdentifier, InterfaceType,
    Interfaces, MergedInterfaces,
};

#[test]
fn test_ethernet_stringlized_attributes() {
    let iface: EthernetInterface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: up
ethernet:
  auto-negotiation: "false"
  speed: "1000"
  sr-iov:
    drivers-autoprobe: "false"
    total-vfs: "64"
    vfs:
      - id: "0"
        spoof-check: "true"
        trust: "false"
        min-tx-rate: "100"
        max-tx-rate: "101"
        vlan-id: "102"
        qos: "103"
"#,
    )
    .unwrap();

    let eth_conf = iface.ethernet.unwrap();
    let sriov_conf = eth_conf.sr_iov.as_ref().unwrap();
    let vf_conf = sriov_conf.vfs.as_ref().unwrap().first().unwrap();

    assert_eq!(eth_conf.speed, Some(1000));
    assert_eq!(sriov_conf.drivers_autoprobe, Some(false));
    assert_eq!(sriov_conf.total_vfs, Some(64));
    assert_eq!(vf_conf.id, 0);
    assert_eq!(vf_conf.spoof_check, Some(true));
    assert_eq!(vf_conf.trust, Some(false));
    assert_eq!(vf_conf.min_tx_rate, Some(100));
    assert_eq!(vf_conf.max_tx_rate, Some(101));
    assert_eq!(vf_conf.vlan_id, Some(102));
    assert_eq!(vf_conf.qos, Some(103));
}

#[test]
fn test_veth_change_peer_away_from_ignored_peer() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: veth1
  type: veth
  state: up
  veth:
    peer: newpeer
",
    )
    .unwrap();
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: veth1
  type: veth
  state: up
  veth:
    peer: veth1peer

- name: veth1peer
  type: veth
  state: ignore
  veth:
    peer: veth1
",
    )
    .unwrap();

    let result = MergedInterfaces::new(des_ifaces, cur_ifaces, false, false);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_veth_change_peer_away_from_missing_peer() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: veth1
          type: veth
          state: up
          veth:
            peer: newpeer
        ",
    )
    .unwrap();
    // The peer of veth1 does not exist in current state means the veth peer is
    // in another network namespace
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: veth1
          type: veth
          state: up
        ",
    )
    .unwrap();

    let result = MergedInterfaces::new(des_ifaces, cur_ifaces, false, false);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_eth_verify_absent_ignore_current_up() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: eth1
  type: ethernet
  state: absent
",
    )
    .unwrap();
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: eth1
  type: ethernet
  state: up
",
    )
    .unwrap();
    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces.clone(), false, false)
            .unwrap();

    merged_ifaces.verify(&cur_ifaces).unwrap();
}

#[test]
fn test_eth_change_veth_peer() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: veth1
  type: veth
  state: up
  veth:
    peer: newpeer
",
    )
    .unwrap();
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: veth1
  type: veth
  state: up
  veth:
    peer: veth1peer

- name: veth1peer
  type: veth
  state: up
  veth:
    peer: veth1
",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();

    let old_peer_iface = merged_ifaces
        .get_iface("veth1peer", InterfaceType::Unknown)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert!(old_peer_iface.is_absent());
}

#[test]
fn test_new_veth_without_peer_config() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
- name: veth1
  type: veth
  state: up
",
    )
    .unwrap();

    let result =
        MergedInterfaces::new(des_ifaces, Interfaces::new(), false, false);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("interface veth1 does not exist"));
    }
}

#[test]
fn test_mac_identifer_use_permanent_mac_first() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: eth1
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1b
          permanent-mac-address: 00:23:45:67:89:1a
        - name: eth2
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1b
          permanent-mac-address: 00:23:45:67:89:1b
        ",
    )
    .unwrap();

    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: wan0
          type: ethernet
          state: up
          identifier: mac-address
          mac-address: 00:23:45:67:89:1b
        ",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();

    let des_iface = merged_ifaces
        .kernel_ifaces
        .get("eth2")
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(
        des_iface.base_iface().identifier.as_ref(),
        Some(InterfaceIdentifier::MacAddress).as_ref()
    );
    assert_eq!(des_iface.base_iface().profile_name.as_deref(), Some("wan0"))
}

#[test]
fn test_mac_identifer_use_fallback_to_mac() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: eth1
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1b
          permanent-mac-address: 00:23:45:67:89:1a
        - name: eth2
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1b
          permanent-mac-address: 00:23:45:67:89:1b
        - name: eth3
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1c
        ",
    )
    .unwrap();

    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: wan0
          type: ethernet
          state: up
          identifier: mac-address
          mac-address: 00:23:45:67:89:1c
        ",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();

    let des_iface = merged_ifaces
        .kernel_ifaces
        .get("eth3")
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(
        des_iface.base_iface().identifier.as_ref(),
        Some(InterfaceIdentifier::MacAddress).as_ref()
    );
    assert_eq!(des_iface.base_iface().profile_name.as_deref(), Some("wan0"))
}

#[test]
fn test_mac_identifer_check_iface_type_also() {
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: bond0
          type: bond
          state: up
          mac-address: 00:23:45:67:89:1b
          link-aggregation:
            mode: balance-rr
            port:
            - eth2
            - eth1
        - name: eth1
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1b
          permanent-mac-address: 00:23:45:67:89:1a
        - name: eth2
          type: ethernet
          state: up
          mac-address: 00:23:45:67:89:1b
          permanent-mac-address: 00:23:45:67:89:1b
        ",
    )
    .unwrap();

    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: wan0
          type: ethernet
          state: up
          identifier: mac-address
          mac-address: 00:23:45:67:89:1b
        ",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, cur_ifaces, false, false).unwrap();

    let des_iface = merged_ifaces
        .kernel_ifaces
        .get("eth2")
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(
        des_iface.base_iface().identifier.as_ref(),
        Some(InterfaceIdentifier::MacAddress).as_ref()
    );
    assert_eq!(des_iface.base_iface().profile_name.as_deref(), Some("wan0"))
}
