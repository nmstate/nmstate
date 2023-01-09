// SPDX-License-Identifier: Apache-2.0

use crate::{
    BondMode, ErrorKind, InfiniBandInterface, Interface, InterfaceType,
    Interfaces, MergedInterfaces,
};

#[test]
fn test_ib_autoremove_pkey_if_base_iface_removed() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: mlx5_ib2
  type: infiniband
  state: absent
"#,
    )
    .unwrap();
    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: mlx5_ib2
  type: infiniband
  state: up
  infiniband:
    pkey: "0xffff"
    mode: "connected"
- name: mlx5_ib2.8001
  type: infiniband
  state: up
  infiniband:
    pkey: "0x8001"
    mode: "connected"
    base-iface: "mlx5_ib2"
"#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let iface = merged_ifaces
        .get_iface("mlx5_ib2", InterfaceType::InfiniBand)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    assert!(iface.is_absent());

    let iface = merged_ifaces
        .get_iface("mlx5_ib2.8001", InterfaceType::InfiniBand)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();
    assert!(iface.is_absent());
}

#[test]
fn test_ib_support_integer_pkey() {
    let iface: InfiniBandInterface = serde_yaml::from_str(
        r#"---
name: mlx5_ib2.8001
type: infiniband
state: up
infiniband:
  pkey: 32769
  mode: "connected"
  base-iface: "mlx5_ib2"
"#,
    )
    .unwrap();
    assert_eq!(iface.ib.unwrap().pkey, Some(0x8001));
}

#[test]
fn test_ib_support_string_pkey() {
    let iface: InfiniBandInterface = serde_yaml::from_str(
        r#"---
name: mlx5_ib2.8001
type: infiniband
state: up
infiniband:
  pkey: "32769"
  mode: "connected"
  base-iface: "mlx5_ib2"
"#,
    )
    .unwrap();
    assert_eq!(iface.ib.unwrap().pkey, Some(0x8001));
}

#[test]
fn test_ib_support_hex_string_pkey() {
    let iface: InfiniBandInterface = serde_yaml::from_str(
        r#"---
name: mlx5_ib2.8001
type: infiniband
state: up
infiniband:
  pkey: "0x8001"
  mode: "connected"
  base-iface: "mlx5_ib2"
"#,
    )
    .unwrap();
    assert_eq!(iface.ib.unwrap().pkey, Some(0x8001));
}

#[test]
fn test_ib_port_of_bridge_in_desire() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: mlx5_ib2
  type: infiniband
  state: up
  infiniband:
    pkey: "0xffff"
    mode: "connected"
- name: br0
  type: linux-bridge
  bridge:
    port:
    - name: mlx5_ib2
"#,
    )
    .unwrap();

    let result =
        MergedInterfaces::new(desired, Interfaces::new(), false, false);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ib_port_of_bridge_in_current() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: br0
  type: linux-bridge
  bridge:
    port:
    - name: mlx5_ib2
"#,
    )
    .unwrap();

    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: mlx5_ib2
  type: infiniband
  state: up
  infiniband:
    pkey: "0xffff"
    mode: "connected"
"#,
    )
    .unwrap();

    let result = MergedInterfaces::new(desired, current, false, false);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ib_port_of_bond_mode_in_desire() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: bond0
  type: bond
  state: up
  link-aggregation:
    mode: balance-rr
    port:
    - mlx5_ib2
"#,
    )
    .unwrap();

    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: mlx5_ib2
  type: infiniband
  state: up
  infiniband:
    pkey: "0xffff"
    mode: "connected"
"#,
    )
    .unwrap();

    let result = MergedInterfaces::new(desired, current, false, false);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ib_port_of_bond_mode_in_current() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: bond0
  type: bond
  state: up
  link-aggregation:
    port:
    - mlx5_ib2
"#,
    )
    .unwrap();

    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: mlx5_ib2
  type: infiniband
  state: up
  infiniband:
    pkey: "0xffff"
    mode: "connected"
- name: bond0
  type: bond
  state: up
  link-aggregation:
    mode: balance-rr
    port:
    - mlx5_ib2
"#,
    )
    .unwrap();

    let result = MergedInterfaces::new(desired, current, false, false);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ib_port_of_active_backup_bond_mode_in_current() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: bond0
  type: bond
  state: up
  link-aggregation:
    port:
    - mlx5_ib2
"#,
    )
    .unwrap();

    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: mlx5_ib2
  type: infiniband
  state: up
  infiniband:
    pkey: "0xffff"
    mode: "connected"
- name: bond0
  type: bond
  state: up
  link-aggregation:
    mode: active-backup
    port:
    - mlx5_ib2
"#,
    )
    .unwrap();

    MergedInterfaces::new(desired, current, false, false).unwrap();
}

#[test]
fn test_ib_port_of_active_backup_bond_mode_in_both() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: bond0
  type: bond
  state: up
  link-aggregation:
    mode: active-backup
    port:
    - mlx5_ib2
"#,
    )
    .unwrap();

    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: mlx5_ib2
  type: infiniband
  state: up
  infiniband:
    pkey: "0xffff"
    mode: "connected"
- name: bond0
  type: bond
  state: up
  link-aggregation:
    mode: balance-rr
    port:
    - mlx5_ib2
"#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let iface = merged_ifaces
        .get_iface("bond0", InterfaceType::Bond)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    if let Interface::Bond(iface) = iface {
        assert_eq!(
            iface.bond.as_ref().unwrap().mode.as_ref(),
            Some(&BondMode::ActiveBackup)
        );
    } else {
        panic!("Expecting a bond interface but got {:?}", iface);
    }
}

#[test]
fn test_ib_port_of_active_backup_bond_mode_in_desire() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: bond0
  type: bond
  state: up
  link-aggregation:
    mode: active-backup
    port:
    - mlx5_ib2
"#,
    )
    .unwrap();

    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: mlx5_ib2
  type: infiniband
  state: up
  infiniband:
    pkey: "0xffff"
    mode: "connected"
"#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let iface = merged_ifaces
        .get_iface("mlx5_ib2", InterfaceType::InfiniBand)
        .unwrap()
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(iface.base_iface().controller.as_deref(), Some("bond0"));

    assert_eq!(
        iface.base_iface().controller_type.as_ref(),
        Some(&InterfaceType::Bond)
    );
}
