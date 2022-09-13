// SPDX-License-Identifier: Apache-2.0

use crate::{BaseInterface, ErrorKind};

#[test]
fn test_valid_mptcp_flags() {
    let iface: BaseInterface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: up
mptcp:
  address-flags:
  - signal
  - fullmesh
"#,
    )
    .unwrap();
    let result = iface.validate(Some(&BaseInterface::new()));
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_mptcp_pre_edit_cleanup() {
    let mut desire_iface: BaseInterface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: up
mptcp:
  address-flags:
  - signal
  - backup
  - fullmesh
ipv4:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "192.168.1.1"
    prefix-length: "24"
    mptcp-flags:
    - signal
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
  - signal
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

    desire_iface.pre_edit_cleanup(None).unwrap();
    assert_eq!(desire_iface, expected_iface);
}
