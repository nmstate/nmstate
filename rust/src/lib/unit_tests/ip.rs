// SPDX-License-Identifier: Apache-2.0

use crate::{
    unit_tests::testlib::new_eth_iface, BaseInterface, ErrorKind, Interface,
    InterfaceState, Interfaces, MergedInterfaces,
};

fn gen_test_eth_ifaces() -> Interfaces {
    let mut ifaces = Interfaces::new();
    ifaces.push(new_eth_iface("eth1"));
    ifaces
}

#[test]
fn test_ip_stringlized_attributes() {
    let iface: BaseInterface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: up
ipv4:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "192.168.1.1"
    prefix-length: "24"
ipv6:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
    prefix-length: "64"
"#,
    )
    .unwrap();
    let ipv4_conf = iface.ipv4.unwrap();
    let ipv6_conf = iface.ipv6.unwrap();

    assert!(ipv4_conf.enabled);
    assert_eq!(ipv4_conf.dhcp, Some(false));
    assert_eq!(
        ipv4_conf.addresses.as_deref().unwrap()[0].ip.to_string(),
        "192.168.1.1"
    );
    assert_eq!(ipv4_conf.addresses.as_deref().unwrap()[0].prefix_length, 24);
    assert!(ipv6_conf.enabled);
    assert_eq!(
        ipv6_conf.addresses.as_deref().unwrap()[0].ip.to_string(),
        "2001:db8:85a3::8a2e:370:7331",
    );
    assert_eq!(ipv6_conf.addresses.as_deref().unwrap()[0].prefix_length, 64);
}

#[test]
fn test_ip_ignore_deserialize_error_of_absent_iface() {
    let iface: Interface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: absent
ipv4:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "g.g.g.g"
    prefix-length: "24"
ipv6:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "::g"
    prefix-length: "64"
"#,
    )
    .unwrap();
    assert_eq!(iface.base_iface().state, InterfaceState::Absent);
    assert_eq!(iface.name(), "eth1");
    assert_eq!(iface.base_iface().ipv4, None);
    assert_eq!(iface.base_iface().ipv6, None);
}

#[test]
fn test_ip_allow_extra_address_by_default() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv4:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "192.168.1.1"
      prefix-length: "24"
  ipv6:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
      prefix-length: "64"
"#,
    )
    .unwrap();
    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv4:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "192.168.1.1"
      prefix-length: "24"
    - ip: "192.168.1.2"
      prefix-length: "24"
  ipv6:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
      prefix-length: "64"
    - ip: "2001:0db8:85a3:0000:0001:8a2e:0370:7331"
      prefix-length: "64"
"#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, gen_test_eth_ifaces(), false, false)
            .unwrap();

    merged_ifaces.verify(&current).unwrap();
}

#[test]
fn test_ipv4_not_allow_extra_address() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv4:
    enabled: "true"
    dhcp: "false"
    allow-extra-address: false
    address:
    - ip: "192.168.1.1"
      prefix-length: "24"
"#,
    )
    .unwrap();
    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv4:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "192.168.1.1"
      prefix-length: "24"
    - ip: "192.168.1.2"
      prefix-length: "24"
"#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, gen_test_eth_ifaces(), false, false)
            .unwrap();

    let result = merged_ifaces.verify(&current);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::VerificationError);
    }
}

#[test]
fn test_ipv6_not_allow_extra_address() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv6:
    enabled: "true"
    dhcp: "false"
    allow-extra-address: false
    address:
    - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
      prefix-length: "64"
"#,
    )
    .unwrap();
    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv6:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
      prefix-length: "64"
    - ip: "2001:0db8:85a3:0000:0001:8a2e:0370:7331"
      prefix-length: "64"
"#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, gen_test_eth_ifaces(), false, false)
            .unwrap();

    let result = merged_ifaces.verify(&current);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::VerificationError);
    }
}

#[test]
fn test_ipv6_mtu_lower_than_1280() {
    let mut iface: BaseInterface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: up
mtu: 1279
ipv6:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
    prefix-length: "64"
"#,
    )
    .unwrap();

    let result = iface.sanitize(true);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("MTU should be >= 1280"));
    }
}

#[test]
fn test_ipv6_verify_emtpy() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
            - name: eth1
              type: ethernet
              state: up
              ipv6:
                enabled: "true"
                dhcp: "false"
                address: []"#,
    )
    .unwrap();

    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
            - name: eth1
              type: ethernet
              state: up
              ipv6:
                enabled: "true"
                dhcp: "false""#,
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(des_ifaces, gen_test_eth_ifaces(), false, false)
            .unwrap();

    merged_ifaces.verify(&cur_ifaces).unwrap();
}
