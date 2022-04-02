use crate::BaseInterface;

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
