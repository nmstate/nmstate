use crate::{BondInterface, ErrorKind, Interface};

#[test]
fn test_bond_validate_mac_restricted_with_mac_undefined() {
    let iface: BondInterface = serde_yaml::from_str(
        r#"---
name: bond99
type: bond
state: up
link-aggregation:
  mode: active-backup
  options:
    fail_over_mac: active
"#,
    )
    .unwrap();
    iface.validate(None).unwrap();
}

#[test]
fn test_bond_validate_mac_restricted_with_mac_defined() {
    let iface: BondInterface = serde_yaml::from_str(
        r#"---
name: bond99
type: bond
state: up
mac-address: 00:01:02:03:04:05
link-aggregation:
  mode: active-backup
  options:
    fail_over_mac: active
"#,
    )
    .unwrap();
    let result = iface.validate(None);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_bond_validate_mac_restricted_with_mac_defined_for_exist_bond() {
    let iface: BondInterface = serde_yaml::from_str(
        r#"---
name: bond99
type: bond
state: up
mac-address: 00:01:02:03:04:05
"#,
    )
    .unwrap();
    let current_iface: Interface = serde_yaml::from_str(
        r#"---
name: bond99
type: bond
state: up
link-aggregation:
  mode: active-backup
  options:
    fail_over_mac: active
"#,
    )
    .unwrap();
    let result = iface.validate(Some(&current_iface));
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_bond_validate_mac_restricted_with_mac_defined_changing_mode() {
    let iface: BondInterface = serde_yaml::from_str(
        r#"---
name: bond99
type: bond
state: up
mac-address: 00:01:02:03:04:05
link-aggregation:
  mode: 802.3ad
"#,
    )
    .unwrap();
    let current_iface: Interface = serde_yaml::from_str(
        r#"---
name: bond99
type: bond
state: up
link-aggregation:
  mode: active-backup
  options:
    fail_over_mac: active
"#,
    )
    .unwrap();
    iface.validate(Some(&current_iface)).unwrap();
}

#[test]
fn test_bond_validate_mac_restricted_with_mac_defined_changing_opt() {
    let iface: BondInterface = serde_yaml::from_str(
        r#"---
name: bond99
type: bond
state: up
mac-address: 00:01:02:03:04:05
link-aggregation:
  mode: active-backup
  options:
    fail_over_mac: follow
"#,
    )
    .unwrap();
    let current_iface: Interface = serde_yaml::from_str(
        r#"---
name: bond99
type: bond
state: up
link-aggregation:
  mode: active-backup
  options:
    fail_over_mac: active
"#,
    )
    .unwrap();
    iface.validate(Some(&current_iface)).unwrap();
}

#[test]
fn test_bond_validate_bond_mode_not_defined_for_new_iface() {
    let iface: BondInterface = serde_yaml::from_str(
        r#"---
name: bond99
type: bond
state: up
"#,
    )
    .unwrap();
    let result = iface.validate(None);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_bond_validate_ad_actor_system_mac_address() {
    let iface: BondInterface = serde_yaml::from_str(
        r#"---
name: bond99
type: bond
state: up
link-aggregation:
  mode: 802.3ad
  options:
    ad_actor_system: "01:00:5E:00:0f:01"
"#,
    )
    .unwrap();
    let result = iface.validate(None);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_bond_validate_miimon_and_arp_interval() {
    let iface: BondInterface = serde_yaml::from_str(
        r#"---
name: bond99
type: bond
state: up
link-aggregation:
  mode: 802.3ad
  options:
    miimon: 100
    arp_interval: 60
"#,
    )
    .unwrap();
    let result = iface.validate(None);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}
