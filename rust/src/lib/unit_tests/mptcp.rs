// SPDX-License-Identifier: Apache-2.0

use crate::{BaseInterface, ErrorKind, Interface, MergedInterface};

#[test]
fn test_valid_mptcp_flags() {
    let des_iface: Interface = serde_yaml::from_str(
        r"---
name: eth1
type: ethernet
state: up
mptcp:
  address-flags:
  - signal
  - fullmesh
",
    )
    .unwrap();

    let mut merged_iface = MergedInterface::new(Some(des_iface), None).unwrap();

    let result = merged_iface.post_inter_ifaces_process();
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_mptcp_sanitize_remove_per_addr_flag() {
    let mut des_iface: BaseInterface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: up
mptcp:
  address-flags:
  - backup
  - fullmesh
ipv4:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "192.168.1.1"
    prefix-length: "24"
    mptcp-flags:
    - backup
    - fullmesh
ipv6:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
    prefix-length: "64"
    mptcp-flags:
    - signal
    - backup
    - fullmesh
"#,
    )
    .unwrap();
    let expected_iface: BaseInterface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: up
mptcp:
  address-flags:
  - backup
  - fullmesh
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

    des_iface.sanitize(true).unwrap();

    assert_eq!(des_iface, expected_iface);
}
