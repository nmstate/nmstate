use crate::{
    unit_tests::testlib::{
        new_eth_iface, new_ovs_br_iface, new_ovs_iface, new_unknown_iface,
        new_vlan_iface,
    },
    InterfaceState, InterfaceType, Interfaces,
};

#[test]
fn test_resolve_unknown_type_absent_eth() {
    let mut cur_ifaces = Interfaces::new();
    cur_ifaces.push(new_eth_iface("eth2"));
    cur_ifaces.push(new_eth_iface("eth1"));

    let mut absent_iface = new_unknown_iface("eth1");
    absent_iface.base_iface_mut().state = InterfaceState::Absent;
    let mut ifaces = Interfaces::new();
    ifaces.push(absent_iface);

    ifaces.resolve_unknown_ifaces(&cur_ifaces).unwrap();
    let (_, _, del_ifaces) = ifaces.gen_state_for_apply(&cur_ifaces).unwrap();

    let del_ifaces = del_ifaces.to_vec();

    assert_eq!(del_ifaces[0].name(), "eth1");
    assert_eq!(del_ifaces[0].iface_type(), InterfaceType::Ethernet);
    assert!(del_ifaces[0].is_absent());
    assert!(ifaces.user_ifaces.is_empty());
}

#[test]
fn test_resolve_unknown_type_absent_multiple() {
    let mut cur_ifaces = Interfaces::new();
    cur_ifaces.push(new_ovs_br_iface("br0", &["p1", "p2"]));
    cur_ifaces.push(new_ovs_iface("br0", "br0"));
    cur_ifaces.push(new_ovs_iface("p1", "br0"));

    let mut absent_iface = new_unknown_iface("br0");
    absent_iface.base_iface_mut().state = InterfaceState::Absent;
    let mut ifaces = Interfaces::new();
    ifaces.push(absent_iface);

    let (_, _, del_ifaces) = ifaces.gen_state_for_apply(&cur_ifaces).unwrap();

    let del_ifaces = del_ifaces.to_vec();

    assert_eq!(del_ifaces[0].name(), "br0");
    assert_eq!(del_ifaces[0].iface_type(), InterfaceType::OvsInterface);
    assert!(del_ifaces[0].is_absent());
    assert_eq!(del_ifaces[1].name(), "br0");
    assert_eq!(del_ifaces[1].iface_type(), InterfaceType::OvsBridge);
    assert!(del_ifaces[1].is_absent());
}

#[test]
fn test_mark_orphan_vlan_as_absent() {
    let mut current = Interfaces::new();
    current.push(new_eth_iface("eth0"));
    current.push(new_vlan_iface("eth0.10", "eth0", 10));

    let mut desired = Interfaces::new();
    let mut eth0 = new_eth_iface("eth0");
    eth0.base_iface_mut().state = InterfaceState::Absent;
    desired.push(eth0);

    let (_, _, del_ifaces) = desired.gen_state_for_apply(&current).unwrap();
    assert_eq!(del_ifaces.to_vec().len(), 2);
    assert!(del_ifaces.kernel_ifaces["eth0"].is_absent());
    assert!(del_ifaces.kernel_ifaces["eth0.10"].is_absent());
}

#[test]
fn test_check_orphan_vlan_change_parent() {
    let mut current = Interfaces::new();
    current.push(new_eth_iface("eth0"));
    current.push(new_vlan_iface("eth0.10", "eth0", 10));

    let mut desired = Interfaces::new();
    let mut eth0 = new_eth_iface("eth0");
    eth0.base_iface_mut().state = InterfaceState::Absent;
    desired.push(eth0);
    desired.push(new_vlan_iface("eth0.10", "eth1", 10));
    desired.push(new_eth_iface("eth1"));

    let (_, chg_ifaces, del_ifaces) =
        desired.gen_state_for_apply(&current).unwrap();
    assert_eq!(del_ifaces.to_vec().len(), 1);
    assert!(del_ifaces.kernel_ifaces["eth0"].is_absent());
    assert!(!chg_ifaces.kernel_ifaces["eth0.10"].is_absent());
}
