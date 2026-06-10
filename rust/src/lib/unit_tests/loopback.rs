// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, Interfaces, MergedInterfaces};

fn gen_lo_ifaces(ipv6_enabled: bool) -> Interfaces {
    let yml = if ipv6_enabled {
        r#"---
- name: lo
  type: loopback
  state: up
  mtu: 65536
  ipv4:
    enabled: true
    address:
    - ip: 127.0.0.1
      prefix-length: 8
  ipv6:
    enabled: true
    address:
    - ip: ::1
      prefix-length: 128
"#
    } else {
        r#"---
- name: lo
  type: loopback
  state: up
  mtu: 65536
  ipv4:
    enabled: true
    address:
    - ip: 127.0.0.1
      prefix-length: 8
  ipv6:
    enabled: false
"#
    };
    serde_yaml::from_str(yml).unwrap()
}

fn gen_lo_ipv4_disabled_ifaces() -> Interfaces {
    serde_yaml::from_str(
        r#"---
- name: lo
  type: loopback
  state: up
  ipv4:
    enabled: false
"#,
    )
    .unwrap()
}

#[test]
fn test_loopback_allow_ipv6_disabled_when_currently_disabled() {
    // On a system booted with `ipv6.disable=1`, `nmstatectl show` reports
    // loopback with IPv6 disabled. Reapplying that output should not fail.
    let desired = gen_lo_ifaces(false);
    let current = gen_lo_ifaces(false);

    MergedInterfaces::new(desired, current, Default::default(), false).unwrap();
}

#[test]
fn test_loopback_allow_partial_ipv6_disabled_when_currently_disabled() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: lo
  type: loopback
  state: up
  ipv6:
    enabled: false
"#,
    )
    .unwrap();
    let current = gen_lo_ifaces(false);

    MergedInterfaces::new(desired, current, Default::default(), false).unwrap();
}

#[test]
fn test_loopback_allow_enable_ipv6_when_currently_disabled() {
    let desired = gen_lo_ifaces(true);
    let current = gen_lo_ifaces(false);

    MergedInterfaces::new(desired, current, Default::default(), false).unwrap();
}

#[test]
fn test_loopback_reject_ipv6_disabled_when_currently_enabled() {
    let desired = gen_lo_ifaces(false);
    let current = gen_lo_ifaces(true);

    let e = MergedInterfaces::new(desired, current, Default::default(), false)
        .unwrap_err();
    assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    assert!(e.msg().contains("IPv6"));
}

#[test]
fn test_loopback_reject_ipv6_disabled_when_current_ipv6_unknown() {
    let desired = gen_lo_ifaces(false);
    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: lo
  type: loopback
  state: up
  mtu: 65536
  ipv4:
    enabled: true
    address:
    - ip: 127.0.0.1
      prefix-length: 8
"#,
    )
    .unwrap();

    let e = MergedInterfaces::new(desired, current, Default::default(), false)
        .unwrap_err();
    assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    assert!(e.msg().contains("IPv6"));
}

#[test]
fn test_loopback_reject_ipv4_disabled_when_currently_enabled() {
    let desired = gen_lo_ipv4_disabled_ifaces();
    let current = gen_lo_ifaces(true);

    let e = MergedInterfaces::new(desired, current, Default::default(), false)
        .unwrap_err();
    assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    assert!(e.msg().contains("IPv4"));
}

#[test]
fn test_loopback_reject_ipv4_disabled_even_when_currently_disabled() {
    // Unlike IPv6, the kernel cannot run with IPv4 disabled. A loopback
    // without IPv4 is a broken state which should not be preserved.
    let desired = gen_lo_ipv4_disabled_ifaces();
    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: lo
  type: loopback
  state: up
  mtu: 65536
  ipv4:
    enabled: false
  ipv6:
    enabled: true
    address:
    - ip: ::1
      prefix-length: 128
"#,
    )
    .unwrap();

    let e = MergedInterfaces::new(desired, current, Default::default(), false)
        .unwrap_err();
    assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    assert!(e.msg().contains("IPv4"));
}

#[test]
fn test_loopback_reject_ipv6_disabled_when_current_unknown() {
    let desired = gen_lo_ifaces(false);

    let e = MergedInterfaces::new(
        desired,
        Interfaces::new(),
        Default::default(),
        false,
    )
    .unwrap_err();
    assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    assert!(e.msg().contains("IPv6"));
}
