use crate::{
    ifaces::get_ignored_ifaces, InterfaceType, Interfaces, OvsBridgeInterface,
};

#[test]
fn test_ovs_bridge_ignore_port() {
    let mut ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: ignore
- name: eth2
  type: ethernet
  state: up
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth2
"#,
    )
    .unwrap();
    let mut cur_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
- name: eth2
  type: ethernet
  state: up
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: eth2
"#,
    )
    .unwrap();

    let (ignored_kernel_ifaces, ignored_user_ifaces) =
        get_ignored_ifaces(&ifaces, &cur_ifaces);

    assert_eq!(ignored_kernel_ifaces, vec!["eth1".to_string()]);
    assert!(ignored_user_ifaces.is_empty());

    ifaces.remove_ignored_ifaces(&ignored_kernel_ifaces, &ignored_user_ifaces);
    cur_ifaces
        .remove_ignored_ifaces(&ignored_kernel_ifaces, &ignored_user_ifaces);

    let (add_ifaces, chg_ifaces, del_ifaces) =
        ifaces.gen_state_for_apply(&cur_ifaces, false).unwrap();

    assert!(!ifaces.kernel_ifaces.contains_key("eth1"));
    assert!(!cur_ifaces.kernel_ifaces.contains_key("eth1"));
    assert_eq!(
        ifaces.user_ifaces[&("br0".to_string(), InterfaceType::OvsBridge)]
            .ports(),
        Some(vec!["eth2"])
    );
    assert_eq!(
        cur_ifaces.user_ifaces[&("br0".to_string(), InterfaceType::OvsBridge)]
            .ports(),
        Some(vec!["eth2"])
    );
    assert!(!add_ifaces.kernel_ifaces.contains_key("eth1"));
    assert!(!chg_ifaces.kernel_ifaces.contains_key("eth1"));
    assert!(!del_ifaces.kernel_ifaces.contains_key("eth1"));
}

#[test]
fn test_ovs_bridge_verify_ignore_port() {
    let ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: ignore
- name: eth2
  type: ethernet
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth2
"#,
    )
    .unwrap();
    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
- name: eth2
  type: ethernet
  state: up
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: eth2
"#,
    )
    .unwrap();

    ifaces.verify(&cur_ifaces).unwrap();
}

#[test]
fn test_ovs_bridge_stringlized_attributes() {
    let iface: OvsBridgeInterface = serde_yaml::from_str(
        r#"---
name: br1
type: ovs-bridge
state: up
bridge:
  options:
    stp: "true"
    rstp: "false"
    mcast-snooping-enable: "false"
  port:
  - name: bond1
    link-aggregation:
      bond-downdelay: "100"
      bond-updelay: "101"
"#,
    )
    .unwrap();

    let br_conf = iface.bridge.unwrap();
    let opts = br_conf.options.as_ref().unwrap();
    let port_conf = &br_conf.ports.as_ref().unwrap()[0];
    let bond_conf = port_conf.bond.as_ref().unwrap();
    assert_eq!(opts.stp, Some(true));
    assert_eq!(opts.rstp, Some(false));
    assert_eq!(opts.mcast_snooping_enable, Some(false));
    assert_eq!(bond_conf.bond_downdelay, Some(100));
    assert_eq!(bond_conf.bond_updelay, Some(101));
}
