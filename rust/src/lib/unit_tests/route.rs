// SPDX-License-Identifier: Apache-2.0

use crate::{
    query_apply::is_route_delayed_by_nm,
    unit_tests::testlib::{
        gen_merged_ifaces_for_route_test, gen_route_entry,
        gen_test_route_entries, gen_test_routes_conf, TEST_IPV4_ADDR1,
        TEST_IPV4_NET1, TEST_IPV6_ADDR1, TEST_IPV6_ADDR2, TEST_IPV6_NET1,
        TEST_IPV6_NET2, TEST_NIC, TEST_ROUTE_METRIC,
    },
    ErrorKind, InterfaceType, Interfaces, MergedRoutes, RouteEntry, RouteState,
    Routes,
};

#[test]
fn test_sort_uniqe_routes() {
    let mut test_routes = gen_test_route_entries();
    test_routes.reverse();
    test_routes.extend(gen_test_route_entries());
    let cur_routes = Routes {
        running: None,
        config: Some(test_routes.clone()),
    };

    let mut dup_route_entry =
        gen_route_entry(TEST_IPV4_NET1, TEST_NIC, TEST_IPV4_ADDR1);
    dup_route_entry.metric = Some(TEST_ROUTE_METRIC + 1);
    test_routes.push(dup_route_entry);

    let mut dup_route_entry =
        gen_route_entry(TEST_IPV6_NET1, TEST_NIC, TEST_IPV6_ADDR1);
    dup_route_entry.metric = Some(TEST_ROUTE_METRIC + 1);
    test_routes.push(dup_route_entry);

    let des_routes = Routes {
        running: None,
        config: Some(test_routes.clone()),
    };

    let (merged_ifaces, current_ifaces) = gen_merged_ifaces_for_route_test();

    let merged_routes =
        MergedRoutes::new(des_routes, Routes::new(), &merged_ifaces).unwrap();

    merged_routes
        .verify(&cur_routes, &[], &current_ifaces)
        .unwrap();

    test_routes.sort_unstable();
    test_routes.dedup();

    assert_eq!(test_routes, gen_test_route_entries());
}

#[test]
fn test_verify_desire_route_not_found() {
    let des_routes = gen_test_routes_conf();

    let mut cur_routes = Routes::new();
    let mut cur_route_entries = gen_test_route_entries();
    cur_route_entries.pop();
    cur_routes.config = Some(cur_route_entries);

    let (merged_ifaces, current_ifaces) = gen_merged_ifaces_for_route_test();

    let merged_routes =
        MergedRoutes::new(des_routes, Routes::new(), &merged_ifaces).unwrap();

    let result = merged_routes.verify(&cur_routes, &[], &current_ifaces);
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

    let (merged_ifaces, current_ifaces) = gen_merged_ifaces_for_route_test();

    let merged_routes =
        MergedRoutes::new(absent_routes, Routes::new(), &merged_ifaces)
            .unwrap();

    let result = merged_routes.verify(&cur_routes, &[], &current_ifaces);
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

    let (merged_ifaces, current_ifaces) = gen_merged_ifaces_for_route_test();

    let merged_routes =
        MergedRoutes::new(des_routes, Routes::new(), &merged_ifaces).unwrap();
    merged_routes
        .verify(&cur_routes, &[], &current_ifaces)
        .unwrap();
}

#[test]
fn test_route_ignore_iface() {
    let routes: Routes = serde_yaml::from_str(
        r"
config:
- destination: 0.0.0.0/0
  next-hop-address: 192.0.2.1
  next-hop-interface: eth1
- destination: ::/0
  next-hop-address: 2001:db8:1::2
  next-hop-interface: eth1
- destination: 0.0.0.0/0
  next-hop-address: 192.0.2.1
  next-hop-interface: eth2
- destination: ::/0
  next-hop-address: 2001:db8:1::2
  next-hop-interface: eth2
",
    )
    .unwrap();

    let (merged_ifaces, _) = gen_merged_ifaces_for_route_test();

    let mut merged_routes =
        MergedRoutes::new(routes, Routes::new(), &merged_ifaces).unwrap();

    let ignored_ifaces = vec![("eth1".to_string(), InterfaceType::Ethernet)];

    merged_routes.remove_routes_to_ignored_ifaces(ignored_ifaces.as_slice());

    let config_routes = merged_routes.indexed.get("eth2").unwrap();

    assert_eq!(merged_routes.route_changed_ifaces, vec!["eth2".to_string()]);
    assert_eq!(config_routes.len(), 2);
    assert_eq!(config_routes[0].next_hop_iface, Some("eth2".to_string()));
    assert_eq!(config_routes[1].next_hop_iface, Some("eth2".to_string()));
}

#[test]
fn test_route_verify_ignore_iface() {
    let desire: Routes = serde_yaml::from_str(
        r"
config:
- destination: 0.0.0.0/0
  state: absent
- destination: ::/0
  state: absent
",
    )
    .unwrap();
    let current: Routes = serde_yaml::from_str(
        r"
config:
- destination: 0.0.0.0/0
  next-hop-address: 192.0.2.1
  next-hop-interface: eth1
- destination: ::/0
  next-hop-address: 2001:db8:1::2
  next-hop-interface: eth1
",
    )
    .unwrap();

    let (merged_ifaces, current_ifaces) = gen_merged_ifaces_for_route_test();

    let mut merged_routes =
        MergedRoutes::new(desire, Routes::new(), &merged_ifaces).unwrap();

    let ignored_ifaces = vec![("eth1".to_string(), InterfaceType::Ethernet)];

    merged_routes.remove_routes_to_ignored_ifaces(ignored_ifaces.as_slice());

    merged_routes
        .verify(&current, &["eth1"], &current_ifaces)
        .unwrap();
}

#[test]
fn test_route_stringlized_attributes() {
    let route: RouteEntry = serde_yaml::from_str(
        r#"
metric: "500"
table-id: "129"
"#,
    )
    .unwrap();
    assert_eq!(route.table_id, Some(129));
    assert_eq!(route.metric, Some(500));
}

#[test]
fn test_route_sanitize_ipv4() {
    let mut route: RouteEntry = serde_yaml::from_str(
        r#"
destination: "192.0.2.1/24"
"#,
    )
    .unwrap();
    route.sanitize().unwrap();
    assert_eq!(route.destination, Some("192.0.2.0/24".to_string()));
}

#[test]
fn test_route_sanitize_ipv4_host() {
    let mut route: RouteEntry = serde_yaml::from_str(
        r#"
destination: "192.0.2.1"
"#,
    )
    .unwrap();
    route.sanitize().unwrap();
    assert_eq!(route.destination, Some("192.0.2.1/32".to_string()));
}

#[test]
fn test_route_sanitize_ipv6() {
    let mut route: RouteEntry = serde_yaml::from_str(
        r#"
destination: "2001:db8:1::1/64"
"#,
    )
    .unwrap();
    route.sanitize().unwrap();
    assert_eq!(route.destination, Some("2001:db8:1::/64".to_string()));
}

#[test]
fn test_route_sanitize_ipv6_host() {
    let mut route: RouteEntry = serde_yaml::from_str(
        r#"
destination: "2001:db8:1::1"
"#,
    )
    .unwrap();
    route.sanitize().unwrap();
    assert_eq!(route.destination, Some("2001:db8:1::1/128".to_string()));
}

#[test]
fn test_route_sanitize_ipv6_host_not_compact() {
    let mut route: RouteEntry = serde_yaml::from_str(
        r#"
destination: "2001:db8:1:0000:000::1"
next-hop-address: "2001:db8:a:0000:000::1"
"#,
    )
    .unwrap();
    route.sanitize().unwrap();
    assert_eq!(route.destination, Some("2001:db8:1::1/128".to_string()));
    assert_eq!(route.next_hop_addr, Some("2001:db8:a::1".to_string()));
}

#[test]
fn test_route_not_allowing_empty_dst() {
    let desired: Routes = serde_yaml::from_str(
        r#"
        config:
        - destination: ""
          state: absent
        "#,
    )
    .unwrap();
    let result = desired.validate();
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("Invalid IP address"));
    }
}

#[test]
fn test_route_sanitize_ipv6_ecmp() {
    let mut route: RouteEntry = serde_yaml::from_str(
        r"
        destination: 2001:db:1::/64
        metric: 150
        next-hop-address: 2001:db8::2
        next-hop-interface: eth1
        weight: 2
        table-id: 254
        ",
    )
    .unwrap();
    let result = route.sanitize();
    assert!(result.is_err());
    assert_eq!(result.err().unwrap().kind(), ErrorKind::NotSupportedError);
}

#[test]
fn test_route_ipv4_ecmp_is_match() {
    let absent_route: RouteEntry = serde_yaml::from_str(
        r"
        destination: 192.0.2.1
        metric: 150
        next-hop-address: 2001:db8::2
        next-hop-interface: eth1
        weight: 2
        table-id: 254
        state: absent
        ",
    )
    .unwrap();
    let route: RouteEntry = serde_yaml::from_str(
        r"
        destination: 192.0.2.1
        metric: 150
        next-hop-address: 2001:db8::2
        next-hop-interface: eth1
        weight: 2
        table-id: 254
        ",
    )
    .unwrap();
    assert!(absent_route.is_match(&route));
}

#[test]
fn test_route_valid_default_gateway() {
    let routes: Routes = serde_yaml::from_str(
        r"
config:
- destination: 0.0.0.0/0
  next-hop-address: 192.0.2.1
  next-hop-interface: eth1
",
    )
    .unwrap();
    routes.validate().unwrap();
}

#[test]
fn test_route_invalid_destination() {
    let routes1: Routes = serde_yaml::from_str(
        r"
config:
- destination: 0.0.0.0/8
  next-hop-address: 192.0.2.1
  next-hop-interface: eth1
",
    )
    .unwrap();
    let result = routes1.validate();
    assert!(result.is_err());
    assert_eq!(result.err().unwrap().kind(), ErrorKind::InvalidArgument);

    let routes2: Routes = serde_yaml::from_str(
        r"
config:
- destination: 0.0.0.0/f
  next-hop-address: 192.0.2.1
  next-hop-interface: eth1
",
    )
    .unwrap();
    let result = routes2.validate();
    assert!(result.is_err());
    assert_eq!(result.err().unwrap().kind(), ErrorKind::InvalidArgument);

    let routes3: Routes = serde_yaml::from_str(
        r"
config:
- destination: 0.0.0.0
  next-hop-address: 192.0.2.1
  next-hop-interface: eth1
",
    )
    .unwrap();
    let result = routes3.validate();
    assert!(result.is_err());
    assert_eq!(result.err().unwrap().kind(), ErrorKind::InvalidArgument);

    let routes4: Routes = serde_yaml::from_str(
        r"
config:
- destination: 0.0.0.0.0/0
  next-hop-address: 192.0.2.1
  next-hop-interface: eth1
",
    )
    .unwrap();
    let result = routes4.validate();
    assert!(result.is_err());
    assert_eq!(result.err().unwrap().kind(), ErrorKind::InvalidArgument);

    let routes5: Routes = serde_yaml::from_str(
        r"
config:
- destination: 0.0.0.0.0/7
  next-hop-address: 192.0.2.1
  next-hop-interface: eth1
",
    )
    .unwrap();
    let result = routes5.validate();
    assert!(result.is_err());
    assert_eq!(result.err().unwrap().kind(), ErrorKind::InvalidArgument);
}

#[test]
fn test_route_matching_empty_via_with_none() {
    let absent_route: RouteEntry = serde_yaml::from_str(
        r#"
        next-hop-address: ""
        state: absent
        "#,
    )
    .unwrap();
    let not_match_route: RouteEntry = serde_yaml::from_str(
        r"
        next-hop-address: 2001:db8::2
        next-hop-interface: eth1
        ",
    )
    .unwrap();
    let match_route: RouteEntry = serde_yaml::from_str(
        r"
        destination: 192.0.2.1
        next-hop-interface: eth1
        ",
    )
    .unwrap();
    assert!(!absent_route.is_match(&not_match_route));
    assert!(!absent_route.is_match(&match_route));
}

#[test]
fn test_routes_delayed_by_nm() {
    let route4: RouteEntry = serde_yaml::from_str(
        r"
        destination: 192.0.2.1
        next-hop-interface: eth0
        ",
    )
    .unwrap();
    let route6: RouteEntry = serde_yaml::from_str(
        r"
        destination: 2001:db:1::/64
        next-hop-interface: eth0
        ",
    )
    .unwrap();

    let current_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: eth0
          type: ethernet
          state: up
          ipv4:
            enabled: true
            dhcp: true
          ipv6:
            enabled: true
            autoconf: true
        ",
    )
    .unwrap();

    assert!(is_route_delayed_by_nm(&route4, &current_ifaces));
    assert!(is_route_delayed_by_nm(&route6, &current_ifaces));
}

#[test]
fn test_routes_not_delayed_by_nm() {
    let route4: RouteEntry = serde_yaml::from_str(
        r"
        destination: 192.0.2.1
        next-hop-interface: eth0
        ",
    )
    .unwrap();
    let route6: RouteEntry = serde_yaml::from_str(
        r"
        destination: 2001:db:1::/64
        next-hop-interface: eth0
        ",
    )
    .unwrap();

    let current_ifaces: Interfaces = serde_yaml::from_str(
        r"---
        - name: eth0
          type: ethernet
          state: up
          ipv4:
            enabled: true
            dhcp: true
            address:
              - ip: 192.168.1.10
                prefix-length: 24
          ipv6:
            enabled: true
            autoconf: true
            address:
              - ip: fc00::1
                prefix-length: 64
        ",
    )
    .unwrap();

    assert!(!is_route_delayed_by_nm(&route4, &current_ifaces));
    assert!(!is_route_delayed_by_nm(&route6, &current_ifaces));
}
