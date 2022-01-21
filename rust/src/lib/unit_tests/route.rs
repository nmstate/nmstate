use crate::{
    unit_tests::testlib::new_eth_iface, ErrorKind, InterfaceType, Interfaces,
    NetworkState, RouteEntry, RouteState, Routes,
};

const TEST_NIC: &str = "eth1";
const TEST_IPV4_NET1: &str = "192.0.2.0/24";
const TEST_IPV4_ADDR1: &str = "198.51.100.1";
const TEST_IPV6_NET1: &str = "2001:db8:1::/64";
const TEST_IPV6_ADDR1: &str = "2001:db8:0::1";
const TEST_IPV6_NET2: &str = "2001:db8:2::/64";
const TEST_IPV6_ADDR2: &str = "2001:db8:0::2";

const TEST_ROUTE_METRIC: i64 = 100;

#[test]
fn test_sort_uniqe_routes() {
    let mut test_routes = gen_test_route_entries();
    test_routes.reverse();
    test_routes.extend(gen_test_route_entries());
    test_routes.push(gen_route_entry(
        TEST_IPV6_NET1,
        TEST_NIC,
        TEST_IPV6_ADDR1,
    ));
    test_routes.push(gen_route_entry(
        TEST_IPV4_NET1,
        TEST_NIC,
        TEST_IPV4_ADDR1,
    ));

    test_routes.sort_unstable();
    test_routes.dedup();

    assert_eq!(test_routes, gen_test_route_entries());
}

#[test]
fn test_add_routes_to_new_interface() {
    let cur_net_state = NetworkState::new();

    let des_iface = new_eth_iface(TEST_NIC);
    let mut des_ifaces = Interfaces::new();
    des_ifaces.push(des_iface);
    let mut des_net_state = NetworkState::new();
    des_net_state.interfaces = des_ifaces;
    des_net_state.routes = gen_test_routes_conf();

    let (add_net_state, chg_net_state, del_net_state) =
        des_net_state.gen_state_for_apply(&cur_net_state).unwrap();

    assert_eq!(chg_net_state, NetworkState::new());
    assert_eq!(del_net_state, NetworkState::new());

    let add_ifaces = add_net_state.interfaces.to_vec();

    assert_eq!(add_ifaces.len(), 1);
    assert_eq!(add_ifaces[0].name(), TEST_NIC);

    let config_routes = add_ifaces[0].base_iface().routes.as_ref().unwrap();
    assert_eq!(config_routes.len(), 2);
    assert_eq!(
        config_routes[0].destination.as_ref().unwrap().as_str(),
        TEST_IPV6_NET1
    );
    assert_eq!(
        config_routes[0].next_hop_iface.as_ref().unwrap().as_str(),
        TEST_NIC
    );
    assert_eq!(
        config_routes[0].next_hop_addr.as_ref().unwrap().as_str(),
        TEST_IPV6_ADDR1
    );
    assert_eq!(
        config_routes[1].destination.as_ref().unwrap().as_str(),
        TEST_IPV4_NET1
    );
    assert_eq!(
        config_routes[1].next_hop_iface.as_ref().unwrap().as_str(),
        TEST_NIC
    );
    assert_eq!(
        config_routes[1].next_hop_addr.as_ref().unwrap().as_str(),
        TEST_IPV4_ADDR1
    );
}

#[test]
fn test_wildcard_absent_routes() {
    let cur_iface = new_eth_iface(TEST_NIC);
    let mut cur_ifaces = Interfaces::new();
    cur_ifaces.push(cur_iface);
    let mut cur_net_state = NetworkState::new();
    cur_net_state.interfaces = cur_ifaces;
    cur_net_state.routes = gen_test_routes_conf();

    let mut des_net_state = NetworkState::new();
    let mut absent_routes = Vec::new();
    let mut absent_route = RouteEntry::new();
    absent_route.state = Some(RouteState::Absent);
    absent_route.next_hop_addr = Some(TEST_IPV4_ADDR1.to_string());
    absent_routes.push(absent_route);
    let mut absent_route = RouteEntry::new();
    absent_route.state = Some(RouteState::Absent);
    absent_route.next_hop_addr = Some(TEST_IPV6_ADDR1.to_string());
    absent_routes.push(absent_route);

    des_net_state.routes.config = Some(absent_routes);

    let (add_net_state, chg_net_state, del_net_state) =
        des_net_state.gen_state_for_apply(&cur_net_state).unwrap();

    assert_eq!(add_net_state, NetworkState::new());
    assert_eq!(del_net_state, NetworkState::new());

    let chg_ifaces = chg_net_state.interfaces.to_vec();

    assert_eq!(chg_ifaces.len(), 1);
    assert_eq!(chg_ifaces[0].base_iface().routes, Some(Vec::new()));
    assert_eq!(chg_ifaces[0].name(), TEST_NIC);
    assert_eq!(chg_ifaces[0].iface_type(), InterfaceType::Ethernet);
}

#[test]
fn test_absent_routes_with_iface_only() {
    let cur_iface = new_eth_iface(TEST_NIC);
    let mut cur_ifaces = Interfaces::new();
    cur_ifaces.push(cur_iface);
    let mut cur_net_state = NetworkState::new();
    cur_net_state.interfaces = cur_ifaces;
    cur_net_state.routes = gen_test_routes_conf();

    let mut des_net_state = NetworkState::new();
    let mut absent_routes = Vec::new();
    let mut absent_route = RouteEntry::new();
    absent_route.state = Some(RouteState::Absent);
    absent_route.next_hop_iface = Some(TEST_NIC.to_string());
    absent_routes.push(absent_route);
    des_net_state.routes.config = Some(absent_routes);

    let (add_net_state, chg_net_state, del_net_state) =
        des_net_state.gen_state_for_apply(&cur_net_state).unwrap();

    assert_eq!(add_net_state, NetworkState::new());
    assert_eq!(del_net_state, NetworkState::new());

    let chg_ifaces = chg_net_state.interfaces.to_vec();

    assert_eq!(chg_ifaces.len(), 1);
    assert_eq!(chg_ifaces[0].base_iface().routes, Some(Vec::new()));
    assert_eq!(chg_ifaces[0].name(), TEST_NIC);
    assert_eq!(chg_ifaces[0].iface_type(), InterfaceType::Ethernet);
}

#[test]
fn test_verify_desire_route_not_found() {
    let des_routes = gen_test_routes_conf();

    let mut cur_routes = Routes::new();
    let mut cur_route_entries = gen_test_route_entries();
    cur_route_entries.pop();
    cur_routes.config = Some(cur_route_entries);

    let result = des_routes.verify(&cur_routes);
    assert!(result.is_err());
    assert_eq!(result.err().unwrap().kind(), ErrorKind::VerificationError);
}

#[test]
fn test_verify_absent_route_still_found() {
    let cur_routes = gen_test_routes_conf();

    let mut absent_routes = Routes::new();
    let mut absent_route_entries = Vec::new();
    let mut absent_route = RouteEntry::new();
    absent_route.state = Some(RouteState::Absent);
    absent_route.next_hop_iface = Some(TEST_NIC.to_string());
    absent_route_entries.push(absent_route);
    absent_routes.config = Some(absent_route_entries);

    let result = absent_routes.verify(&cur_routes);
    assert!(result.is_err());
    assert_eq!(result.err().unwrap().kind(), ErrorKind::VerificationError);
}

#[test]
fn test_verify_current_has_more_routes() {
    let mut cur_routes = gen_test_routes_conf();
    if let Some(config_routes) = cur_routes.config.as_mut() {
        config_routes.push(gen_route_entry(
            TEST_IPV6_NET2,
            TEST_NIC,
            TEST_IPV6_ADDR2,
        ));
    }

    let des_routes = gen_test_routes_conf();

    des_routes.verify(&cur_routes).unwrap();
}

fn gen_test_routes_conf() -> Routes {
    let mut ret = Routes::new();
    ret.running = Some(gen_test_route_entries());
    ret.config = Some(gen_test_route_entries());
    ret
}

fn gen_test_route_entries() -> Vec<RouteEntry> {
    let mut routes = Vec::new();
    routes.push(gen_route_entry(TEST_IPV6_NET1, TEST_NIC, TEST_IPV6_ADDR1));
    routes.push(gen_route_entry(TEST_IPV4_NET1, TEST_NIC, TEST_IPV4_ADDR1));
    routes
}

fn gen_route_entry(
    dst: &str,
    next_hop_iface: &str,
    next_hop_addr: &str,
) -> RouteEntry {
    let mut ret = RouteEntry::new();
    ret.destination = Some(dst.to_string());
    ret.next_hop_iface = Some(next_hop_iface.to_string());
    ret.next_hop_addr = Some(next_hop_addr.to_string());
    ret.metric = Some(TEST_ROUTE_METRIC);
    ret
}
