use crate::{BaseInterface, ErrorKind, Interface, InterfaceState, Interfaces};

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

    desired.verify(&Interfaces::new(), &current).unwrap();
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

    let result = desired.verify(&Interfaces::new(), &current);
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

    let result = desired.verify(&Interfaces::new(), &current);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::VerificationError);
    }
}
