// SPDX-License-Identifier: Apache-2.0

use crate::{
    BaseInterface, ErrorKind, InterfaceType, Interfaces, MergedInterfaces,
};

#[test]
fn test_base_iface_stringlized_attributes() {
    let iface: BaseInterface = serde_yaml::from_str(
        r#"
name: "eth1"
mtu: "1500"
accept-all-mac-addresses: "true"
"#,
    )
    .unwrap();
    assert_eq!(iface.accept_all_mac_addresses, Some(true));
}

#[test]
fn test_base_iface_mac_address_uppercase_before_verification() {
    let mut iface: BaseInterface = serde_yaml::from_str(
        r#"
name: "eth1"
mtu: "1500"
mac-address: "d4:ee:07:25:42:5a"
"#,
    )
    .unwrap();
    iface.sanitize(true).unwrap();
    assert_eq!(iface.mac_address, Some(String::from("D4:EE:07:25:42:5A")));
}

#[test]
fn test_base_iface_serialize_copy_mac_from() {
    let desired: BaseInterface = serde_yaml::from_str(
        r#"---
          name: bond99
          type: bond
          state: up
          copy-mac-from: eth2
        "#,
    )
    .unwrap();

    let new: BaseInterface =
        serde_yaml::from_str(&serde_yaml::to_string(&desired).unwrap())
            .unwrap();

    assert_eq!(desired, new);
}

#[test]
fn test_reject_mtu_exceeding_u32_max() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          type: dummy
          state: up
          mtu: 4294967296
        ",
    )
    .unwrap();

    let err = MergedInterfaces::new(
        desired,
        Interfaces::new(),
        Default::default(),
        false,
    )
    .unwrap_err();
    assert_eq!(err.kind(), ErrorKind::InvalidArgument);
    assert!(err.msg().contains("maximum supported MTU"));
}

#[test]
fn test_accept_mtu_of_u32_max() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          type: dummy
          state: up
          mtu: 4294967295
        ",
    )
    .unwrap();

    let merged = MergedInterfaces::new(
        desired,
        Interfaces::new(),
        Default::default(),
        false,
    )
    .unwrap();
    let iface = merged.get_iface("dummy1", InterfaceType::Dummy).unwrap();
    assert_eq!(iface.merged.base_iface().mtu, Some(u32::MAX as u64));
}
