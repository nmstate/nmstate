// SPDX-License-Identifier: Apache-2.0

use crate::{unit_tests::testlib::gen_test_rule_entries, RouteRuleEntry};

#[test]
fn test_sort_uniqe_route_rules() {
    let mut test_routes = gen_test_rule_entries();
    test_routes.reverse();
    test_routes.extend(gen_test_rule_entries());
    test_routes.sort_unstable();
    test_routes.dedup();

    assert_eq!(test_routes, gen_test_rule_entries());
}

#[test]
fn test_route_rule_stringlized_attributes() {
    let rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
priority: "500"
route-table: "129"
"#,
    )
    .unwrap();
    assert_eq!(rule.table_id, Some(129));
    assert_eq!(rule.priority, Some(500));
}

#[test]
fn test_route_rule_sanitize_ipv4_from_to() {
    let mut rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
ip-to: 192.0.3.1/24
ip-from: 192.0.3.2/24
"#,
    )
    .unwrap();

    rule.sanitize().unwrap();

    assert_eq!(rule.ip_to.unwrap(), "192.0.3.0/24");
    assert_eq!(rule.ip_from.unwrap(), "192.0.3.0/24");
}

#[test]
fn test_route_rule_sanitize_ipv6_from_to() {
    let mut rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
ip-to: 2001:db8:1::2/64
ip-from: 2001:db8:2::ffff/64
"#,
    )
    .unwrap();

    rule.sanitize().unwrap();

    assert_eq!(rule.ip_to.unwrap(), "2001:db8:1::/64");
    assert_eq!(rule.ip_from.unwrap(), "2001:db8:2::/64");
}

#[test]
fn test_route_rule_sanitize_ipv4_from_to_host() {
    let mut rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
ip-to: 192.0.3.1
ip-from: 192.0.3.2
"#,
    )
    .unwrap();

    rule.sanitize().unwrap();

    assert_eq!(rule.ip_to.unwrap(), "192.0.3.1/32");
    assert_eq!(rule.ip_from.unwrap(), "192.0.3.2/32");
}

#[test]
fn test_route_rule_sanitize_ipv6_from_to_host() {
    let mut rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
ip-to: 2001:db8:1::2
ip-from: 2001:db8:2::ffff
"#,
    )
    .unwrap();

    rule.sanitize().unwrap();

    assert_eq!(rule.ip_to.unwrap(), "2001:db8:1::2/128");
    assert_eq!(rule.ip_from.unwrap(), "2001:db8:2::ffff/128");
}

#[test]
fn test_route_rule_sanitize_none_compact_ipv6_from_to() {
    let mut rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
ip-to: 2001:db8:1:0000::2
ip-from: 2001:db8:2:0000::ffff
"#,
    )
    .unwrap();

    rule.sanitize().unwrap();

    assert_eq!(rule.ip_to.unwrap(), "2001:db8:1::2/128");
    assert_eq!(rule.ip_from.unwrap(), "2001:db8:2::ffff/128");
}

#[test]
fn test_route_rule_sanitize_ipv6_family_ip_from() {
    let mut rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
ip-from: 2001:db8:b::/64
priority: 30000
route-table: 200
family: ipv6
"#,
    )
    .unwrap();

    rule.sanitize().unwrap();
}

#[test]
fn test_route_rule_validate_ipv4_family_ip_from() {
    let mut rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
ip-from: 192.168.2.0/24
priority: 30000
route-table: 200
family: ipv4
"#,
    )
    .unwrap();

    rule.sanitize().unwrap();
}
