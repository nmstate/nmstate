use crate::{Interfaces, VlanInterface};

#[test]
fn test_vlan_stringlized_attributes() {
    let iface: VlanInterface = serde_yaml::from_str(
        r#"---
name: vlan1
type: vlan
state: up
vlan:
  base-iface: "eth1"
  id: "101"
"#,
    )
    .unwrap();

    assert_eq!(iface.vlan.unwrap().id, 101);
}

#[test]
fn test_vlan_get_parent_up_priority_plus_one() {
    let mut desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: bond0.100
  type: vlan
  vlan:
    base-iface: bond0
    id: 100
- name: bond0
  type: bond
  link-aggregation:
    mode: balance-rr
- name: vrf0
  type: vrf
  state: up
  vrf:
    port:
    - bond0
    - bond0.100
    route-table-id: 1000"#,
    )
    .unwrap();

    let (add_ifaces, _, _) = desired
        .gen_state_for_apply(&Interfaces::new(), false)
        .unwrap();

    assert_eq!(desired.kernel_ifaces["vrf0"].base_iface().up_priority, 0);
    assert_eq!(desired.kernel_ifaces["bond0"].base_iface().up_priority, 1);
    assert_eq!(
        desired.kernel_ifaces["bond0.100"].base_iface().up_priority,
        2
    );

    let ordered_ifaces = add_ifaces.to_vec();

    assert_eq!(ordered_ifaces[0].name(), "vrf0".to_string());
    assert_eq!(ordered_ifaces[1].name(), "bond0".to_string());
    assert_eq!(ordered_ifaces[2].name(), "bond0.100".to_string());
}
