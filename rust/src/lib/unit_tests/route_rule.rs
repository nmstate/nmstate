// SPDX-License-Identifier: Apache-2.0

use crate::{
    unit_tests::testlib::gen_test_rule_entries, MergedRouteRules,
    RouteRuleEntry, RouteRules,
};

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

#[test]
fn test_route_rule_matching_empty_ip_from_with_none() {
    let absent_rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
        ip-from: ""
        state: absent
        route-table: 200
        "#,
    )
    .unwrap();

    let not_match_rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
        ip-from: 192.168.2.0/24
        priority: 30000
        route-table: 200
        family: ipv4
        "#,
    )
    .unwrap();

    let match_rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
        priority: 30000
        route-table: 200
        family: ipv4
        "#,
    )
    .unwrap();

    assert!(!absent_rule.is_match(&not_match_rule));
    assert!(absent_rule.is_match(&match_rule));
}

#[test]
fn test_route_rule_matching_empty_ip_to_with_none() {
    let absent_rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
        ip-to: ""
        state: absent
        route-table: 200
        "#,
    )
    .unwrap();

    let not_match_rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
        ip-to: 192.168.2.0/24
        priority: 30000
        route-table: 200
        family: ipv4
        "#,
    )
    .unwrap();

    let match_rule: RouteRuleEntry = serde_yaml::from_str(
        r#"
        priority: 30000
        route-table: 200
        family: ipv4
        "#,
    )
    .unwrap();

    assert!(!absent_rule.is_match(&not_match_rule));
    assert!(absent_rule.is_match(&match_rule));
}

#[test]
fn test_route_rule_auto_priority_increasing_from_desire() {
    let des_rules: RouteRules = serde_yaml::from_str(
        r#"
        config:
        - state: absent
          priority: 30001
          route-table: 200
          family: ipv4
        - ip-to: 192.168.2.31
          route-table: 200
          family: ipv4
        - ip-to: 192.168.2.32
          route-table: 200
          family: ipv4
        - ip-to: 192.168.2.33
          route-table: 200
          priority: 30001
          family: ipv4
        "#,
    )
    .unwrap();

    let cur_rules: RouteRules = serde_yaml::from_str(
        r#"
        config:
        - ip-to: 192.168.2.100
          priority: 100
          route-table: 200
          family: ipv4
        - ip-to: 192.168.2.30
          priority: 30001
          route-table: 200
          family: ipv4
        - ip-to: 192.168.2.101
          priority: 101
          route-table: 200
          family: ipv4
        "#,
    )
    .unwrap();

    let merged = MergedRouteRules::new(des_rules, cur_rules).unwrap();

    let mut rules = merged.for_apply;
    rules.sort_unstable();

    assert_eq!(rules.len(), 4);
    assert!(rules[0].is_absent());
    assert_eq!(
        rules[0].ip_to.as_ref().map(|i| i.to_string()),
        Some("192.168.2.30/32".to_string())
    );
    assert_eq!(rules[0].priority, Some(30001));
    assert_eq!(
        rules[1].ip_to.as_ref().map(|i| i.to_string()),
        Some("192.168.2.31/32".to_string())
    );
    assert_eq!(rules[1].priority, Some(30002));
    assert_eq!(
        rules[2].ip_to.as_ref().map(|i| i.to_string()),
        Some("192.168.2.32/32".to_string())
    );
    assert_eq!(rules[2].priority, Some(30003));
    assert_eq!(
        rules[3].ip_to.as_ref().map(|i| i.to_string()),
        Some("192.168.2.33/32".to_string())
    );
    assert_eq!(rules[3].priority, Some(30001));
}

#[test]
fn test_route_rule_auto_priority_increasing_from_empty() {
    let des_rules: RouteRules = serde_yaml::from_str(
        r#"
        config:
        - ip-to: 192.168.2.30
          route-table: 200
          family: ipv4
        - ip-to: 192.168.2.31
          route-table: 200
          family: ipv4
        - ip-to: 192.168.2.32
          route-table: 200
          family: ipv4
        "#,
    )
    .unwrap();

    let cur_rules = RouteRules::new();

    let merged = MergedRouteRules::new(des_rules, cur_rules).unwrap();

    let mut rules = merged.for_apply;
    rules.sort_unstable();

    assert_eq!(rules.len(), 3);
    assert_eq!(
        rules[0].ip_to.as_ref().map(|i| i.to_string()),
        Some("192.168.2.30/32".to_string())
    );
    assert_eq!(rules[0].priority, Some(30000));
    assert_eq!(
        rules[1].ip_to.as_ref().map(|i| i.to_string()),
        Some("192.168.2.31/32".to_string())
    );
    assert_eq!(rules[1].priority, Some(30001));
    assert_eq!(
        rules[2].ip_to.as_ref().map(|i| i.to_string()),
        Some("192.168.2.32/32".to_string())
    );
    assert_eq!(rules[2].priority, Some(30002));
}
