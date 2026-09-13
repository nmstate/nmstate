// SPDX-License-Identifier: Apache-2.0

use crate::{EthernetInterface, VniccConfig};

#[test]
fn test_round_trip_yaml() {
    let yaml = r#"
flooding: true
mcast-flooding: true
learning: true
learning-timeout: 600
"#;
    let cfg: VniccConfig = serde_yaml::from_str(yaml).unwrap();
    assert_eq!(cfg.flooding, Some(true));
    assert_eq!(cfg.learning_timeout, Some(600));
    let back = serde_yaml::to_string(&cfg).unwrap();
    let cfg2: VniccConfig = serde_yaml::from_str(&back).unwrap();
    assert_eq!(cfg, cfg2);
}

#[test]
fn test_learning_timeout_validation() {
    let cfg = VniccConfig {
        learning_timeout: Some(30),
        ..Default::default()
    };
    assert!(cfg.validate().is_err());

    let cfg = VniccConfig {
        learning_timeout: Some(600),
        ..Default::default()
    };
    assert!(cfg.validate().is_ok());

    let cfg = VniccConfig {
        learning_timeout: Some(86401),
        ..Default::default()
    };
    assert!(cfg.validate().is_err());
}

#[test]
fn test_merge_desired_partial() {
    let mut current = VniccConfig {
        flooding: Some(false),
        learning: Some(false),
        learning_timeout: Some(600),
        ..Default::default()
    };
    let desired = VniccConfig {
        flooding: Some(true),
        learning: Some(true),
        ..Default::default() // learning_timeout not specified
    };
    current.merge_desired(&desired);
    assert_eq!(current.flooding, Some(true));
    assert_eq!(current.learning, Some(true));
    // unchanged:
    assert_eq!(current.learning_timeout, Some(600));
}

#[test]
fn test_is_empty() {
    assert!(VniccConfig::default().is_empty());
    let cfg = VniccConfig {
        flooding: Some(true),
        ..Default::default()
    };
    assert!(!cfg.is_empty());
}

#[test]
fn test_vnicc_unknown_field_rejected() {
    let bad_yaml = r#"
flooding: true
unknown-knob: true
"#;
    let result: Result<VniccConfig, _> = serde_yaml::from_str(bad_yaml);
    assert!(result.is_err(), "unknown field should be rejected");
}

#[test]
fn test_qeth_nested_under_ethernet_section() {
    // The `qeth` section lives under the `ethernet` section of an
    // interface, NOT directly under the interface itself.
    let iface: EthernetInterface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: up
ethernet:
  qeth:
    vnicc:
      flooding: true
      mcast-flooding: true
      learning: true
      learning-timeout: 600
"#,
    )
    .unwrap();

    let vnicc = iface
        .ethernet
        .as_ref()
        .and_then(|eth_conf| eth_conf.qeth.as_ref())
        .and_then(|qeth_conf| qeth_conf.vnicc.as_ref())
        .unwrap();
    assert_eq!(vnicc.flooding, Some(true));
    assert_eq!(vnicc.mcast_flooding, Some(true));
    assert_eq!(vnicc.learning, Some(true));
    assert_eq!(vnicc.learning_timeout, Some(600));
}

#[test]
fn test_qeth_directly_under_interface_rejected() {
    // Misplaced interface-level `qeth` must fail to deserialize.
    let result: Result<EthernetInterface, _> = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: up
qeth:
  vnicc:
    flooding: true
"#,
    );
    assert!(result.is_err(), "interface-level qeth should be rejected");
}
