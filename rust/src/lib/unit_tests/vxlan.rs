// SPDX-License-Identifier: Apache-2.0

use crate::VxlanInterface;

#[test]
fn test_vxlan_stringlized_attributes() {
    let iface: VxlanInterface = serde_yaml::from_str(
        r#"---
name: vxlan1
type: vxlan
state: up
vxlan:
  base-iface: "eth1"
  id: "101"
  destination-port: "3389"
"#,
    )
    .unwrap();
    let vxlan_conf = iface.vxlan.unwrap();

    assert_eq!(vxlan_conf.id, 101);
    assert_eq!(vxlan_conf.dst_port, Some(3389));
    assert_eq!(vxlan_conf.learning, None);
}

#[test]
fn test_vxlan_evpn_config_stringlized_attributes() {
    let iface: VxlanInterface = serde_yaml::from_str(
        r#"---
name: vxlan1
type: vxlan
state: up
vxlan:
  id: "101"
  learning: false
  local: "1.2.3.4"
  destination-port: "3389"
"#,
    )
    .unwrap();
    let vxlan_conf = iface.vxlan.unwrap();

    assert!(vxlan_conf.base_iface.is_empty());
    assert_eq!(vxlan_conf.learning, Some(false));
    assert_eq!(
        vxlan_conf.local,
        Some(std::net::IpAddr::V4("1.2.3.4".parse().unwrap()))
    );
}
