use crate::{Interfaces, VrfInterface};

#[test]
fn test_vrf_stringlized_attributes() {
    let iface: VrfInterface = serde_yaml::from_str(
        r#"---
name: vrf1
type: vrf
state: up
vrf:
  route-table-id: "101"
"#,
    )
    .unwrap();

    assert_eq!(iface.vrf.unwrap().table_id, 101);
}

#[test]
fn test_vrf_ports() {
    let ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: vrf1
  type: vrf
  state: up
  vrf:
    route-table-id: "101"
    ports:
      - eth1
      - eth2
"#,
    )
    .unwrap();

    assert_eq!(ifaces.to_vec()[0].ports(), Some(vec!["eth1", "eth2"]));
}
