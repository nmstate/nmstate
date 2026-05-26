// SPDX-License-Identifier: Apache-2.0

use crate::EthernetInterface;

#[test]
fn test_vnicc_deserialize() {
    let iface: EthernetInterface = serde_yaml::from_str(
        r#"---
name: enc600
type: ethernet
state: up
ethernet:
  vnicc:
    bridge-invisible: true
    learning: false
"#,
    )
    .unwrap();

    let eth_conf = iface.ethernet.unwrap();
    let vnicc = eth_conf.vnicc.unwrap();
    assert_eq!(vnicc.bridge_invisible, Some(true));
    assert_eq!(vnicc.learning, Some(false));
}

#[test]
fn test_vnicc_stringlized_attributes() {
    let iface: EthernetInterface = serde_yaml::from_str(
        r#"---
name: enc600
type: ethernet
state: up
ethernet:
  vnicc:
    bridge-invisible: "true"
    learning: "false"
"#,
    )
    .unwrap();

    let eth_conf = iface.ethernet.unwrap();
    let vnicc = eth_conf.vnicc.unwrap();
    assert_eq!(vnicc.bridge_invisible, Some(true));
    assert_eq!(vnicc.learning, Some(false));
}

#[test]
fn test_vnicc_partial_config() {
    let iface: EthernetInterface = serde_yaml::from_str(
        r#"---
name: enc600
type: ethernet
state: up
ethernet:
  vnicc:
    bridge-invisible: true
"#,
    )
    .unwrap();

    let eth_conf = iface.ethernet.unwrap();
    let vnicc = eth_conf.vnicc.unwrap();
    assert_eq!(vnicc.bridge_invisible, Some(true));
    assert_eq!(vnicc.learning, None);
}

#[test]
fn test_vnicc_serialize_skip_none() {
    let iface: EthernetInterface = serde_yaml::from_str(
        r#"---
name: enc600
type: ethernet
state: up
ethernet:
  vnicc:
    bridge-invisible: true
"#,
    )
    .unwrap();

    let yaml = serde_yaml::to_string(&iface).unwrap();
    assert!(yaml.contains("bridge-invisible: true"));
    assert!(!yaml.contains("learning"));
}

#[test]
fn test_ethernet_without_vnicc() {
    let iface: EthernetInterface = serde_yaml::from_str(
        r#"---
name: eth0
type: ethernet
state: up
ethernet:
  auto-negotiation: true
"#,
    )
    .unwrap();

    let eth_conf = iface.ethernet.unwrap();
    assert!(eth_conf.vnicc.is_none());
}
