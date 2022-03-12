use crate::Interfaces;

#[test]
fn test_linux_bridge_ignore_port() {
    let mut ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: ignore
- name: eth2
  type: ethernet
- name: br0
  type: linux-bridge
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
  type: linux-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: eth2
"#,
    )
    .unwrap();

    let ignored_kernel_ifaces = ifaces.ignored_kernel_iface_names();

    assert_eq!(ignored_kernel_ifaces, vec!["eth1".to_string()]);

    let ignored_user_ifaces = ifaces.ignored_user_iface_name_types();
    assert!(ignored_user_ifaces.is_empty());

    ifaces.remove_ignored_ifaces(&ignored_kernel_ifaces, &ignored_user_ifaces);
    cur_ifaces
        .remove_ignored_ifaces(&ignored_kernel_ifaces, &ignored_user_ifaces);

    let (add_ifaces, chg_ifaces, del_ifaces) =
        ifaces.gen_state_for_apply(&cur_ifaces, false).unwrap();

    assert!(!ifaces.kernel_ifaces.contains_key("eth1"));
    assert!(!cur_ifaces.kernel_ifaces.contains_key("eth1"));
    assert_eq!(ifaces.kernel_ifaces["br0"].ports(), Some(vec!["eth2"]));
    assert_eq!(cur_ifaces.kernel_ifaces["br0"].ports(), Some(vec!["eth2"]));
    assert!(!add_ifaces.kernel_ifaces.contains_key("eth1"));
    assert!(!chg_ifaces.kernel_ifaces.contains_key("eth1"));
    assert!(!del_ifaces.kernel_ifaces.contains_key("eth1"));
}

#[test]
fn test_linux_bridge_verify_ignore_port() {
    let ifaces: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: ignore
- name: eth2
  type: ethernet
- name: br0
  type: linux-bridge
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
  type: linux-bridge
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
