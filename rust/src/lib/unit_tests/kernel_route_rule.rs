// SPDX-License-Identifier: Apache-2.0

use nispor::{
    AddressFamily, RouteProtocol, RouteRule, RouteRuleFlag, RuleAction,
};

use crate::{
    ErrorKind, MergedRouteRules, RouteRules,
    nispor::{
        get_route_rules, get_route_rules_for_apply, kernel_rule_is_absent,
    },
};

fn kernel_rule(source: &str, table: u32) -> RouteRule {
    let address: std::net::IpAddr = source.parse().unwrap();
    let mut rule = RouteRule::default();
    rule.address_family = if address.is_ipv4() {
        AddressFamily::Ipv4
    } else {
        AddressFamily::Ipv6
    };
    let prefix = if address.is_ipv4() { 32 } else { 128 };
    rule.src = Some(format!("{address}/{prefix}"));
    rule.action = RuleAction::Table;
    rule.priority = Some(200);
    rule.table = Some(table);
    rule.protocol = Some(RouteProtocol::Boot);
    rule
}

fn merged_rules(desired: &str) -> MergedRouteRules {
    let current: RouteRules = serde_yaml::from_str(
        r"config:
        - family: ipv4
          ip-from: 192.0.2.1/32
          priority: 200
          route-table: 500
        - family: ipv6
          ip-from: 2001:db8::1/128
          priority: 200
          route-table: 500",
    )
    .unwrap();
    MergedRouteRules::new(serde_yaml::from_str(desired).unwrap(), current)
        .unwrap()
}

#[test]
fn test_kernel_route_rule_delete_selectors() {
    for source in ["192.0.2.1", "2001:db8::1"] {
        let merged = merged_rules(&format!(
            "config: [{{state: absent, ip-from: '{source}', route-table: 500, \
             priority: 200}}]"
        ));
        assert!(kernel_rule_is_absent(&kernel_rule(source, 500), &merged));
        assert!(!kernel_rule_is_absent(&kernel_rule(source, 501), &merged));
        for other in ["192.0.2.2", "2001:db8::2"] {
            assert!(!kernel_rule_is_absent(&kernel_rule(other, 500), &merged));
        }
        let mut other_priority = kernel_rule(source, 500);
        other_priority.priority = Some(201);
        assert!(!kernel_rule_is_absent(&other_priority, &merged));
    }
}

#[test]
fn test_kernel_route_rule_delete_wildcard_both_families() {
    let merged = merged_rules("config: [{state: absent, route-table: 500}]");
    for source in ["192.0.2.1", "2001:db8::1"] {
        assert!(kernel_rule_is_absent(&kernel_rule(source, 500), &merged));
        assert!(!kernel_rule_is_absent(&kernel_rule(source, 501), &merged));
    }
}

#[test]
fn test_kernel_route_rule_delete_only_static_protocols() {
    let merged = merged_rules("config: [{state: absent, route-table: 500}]");
    let mut rule = kernel_rule("192.0.2.1", 500);
    for protocol in [
        Some(RouteProtocol::Boot),
        Some(RouteProtocol::Static),
        Some(RouteProtocol::Unspec),
        None,
    ] {
        rule.protocol = protocol;
        assert!(kernel_rule_is_absent(&rule, &merged));
    }
    for protocol in [
        RouteProtocol::Dhcp,
        RouteProtocol::Ra,
        RouteProtocol::KeepAlived,
        RouteProtocol::Babel,
        RouteProtocol::Mrouted,
        RouteProtocol::Bgp,
    ] {
        rule.protocol = Some(protocol);
        assert!(!kernel_rule_is_absent(&rule, &merged));
    }
}

#[test]
fn test_kernel_route_rule_apply_projection_preserves_query() {
    let selected = kernel_rule("192.0.2.1", 500);
    let mut inverted = selected.clone();
    inverted.flags.push(RouteRuleFlag::Invert);
    for protocol in [
        RouteProtocol::Dhcp,
        RouteProtocol::Ra,
        RouteProtocol::KeepAlived,
        RouteProtocol::Babel,
        RouteProtocol::Mrouted,
    ] {
        let mut dynamic = selected.clone();
        dynamic.protocol = Some(protocol);
        let current = [selected.clone(), dynamic, inverted.clone()];
        let queried = get_route_rules(&current, false);
        assert_eq!(queried.config.as_ref().unwrap().len(), 3);
        assert_eq!(
            get_route_rules_for_apply(&current),
            get_route_rules(std::slice::from_ref(&selected), false)
        );
    }
}

#[test]
fn test_kernel_route_rule_absent_preserves_unmanaged_twins() {
    let selected = kernel_rule("192.0.2.1", 500);
    let mut dynamic = selected.clone();
    dynamic.protocol = Some(RouteProtocol::Dhcp);
    let mut inverted = selected.clone();
    inverted.flags.push(RouteRuleFlag::Invert);
    let desired =
        serde_yaml::from_str("config: [{state: absent, route-table: 500}]")
            .unwrap();
    let merged = MergedRouteRules::new(
        desired,
        get_route_rules_for_apply(&[
            selected,
            dynamic.clone(),
            inverted.clone(),
        ]),
    )
    .unwrap();
    assert_eq!(merged.for_apply.len(), 1);
    assert!(merged.for_apply[0].is_absent());
    let remaining = [dynamic, inverted];
    assert_eq!(get_route_rules(&remaining, false).config.unwrap().len(), 2);
    merged
        .verify(&get_route_rules_for_apply(&remaining), &[])
        .unwrap();
}

#[test]
fn test_kernel_route_rule_present_requires_managed_rule() {
    let selected = kernel_rule("192.0.2.1", 500);
    let mut dynamic = selected.clone();
    dynamic.protocol = Some(RouteProtocol::Dhcp);
    let mut inverted = selected.clone();
    inverted.flags.push(RouteRuleFlag::Invert);
    let desired = serde_yaml::from_str(
        r"config:
        - family: ipv4
          ip-from: 192.0.2.1/32
          priority: 200
          route-table: 500
        - state: absent
          route-table: 500",
    )
    .unwrap();
    let current =
        get_route_rules_for_apply(&[dynamic.clone(), inverted.clone()]);
    let merged = MergedRouteRules::new(desired, current.clone()).unwrap();
    assert_eq!(merged.for_apply.len(), 1);
    assert!(!merged.for_apply[0].is_absent());
    assert_eq!(
        merged.verify(&current, &[]).unwrap_err().kind(),
        ErrorKind::VerificationError
    );
    merged
        .verify(
            &get_route_rules_for_apply(&[selected, dynamic, inverted]),
            &[],
        )
        .unwrap();
}

#[test]
fn test_kernel_route_rule_desired_rule_deleted_and_reapplied() {
    let merged = merged_rules(
        r"config:
        - family: ipv4
          ip-from: 192.0.2.1/32
          priority: 200
          route-table: 500
        - state: absent
          route-table: 500",
    );
    assert!(kernel_rule_is_absent(
        &kernel_rule("192.0.2.1", 500),
        &merged
    ));
    assert!(merged.for_apply.iter().any(|rule| {
        !rule.is_absent()
            && rule.ip_from.as_deref() == Some("192.0.2.1/32")
            && rule.table_id == Some(500)
    }));
}

#[test]
fn test_kernel_route_rule_inverted_never_absent() {
    let merged = merged_rules(
        "config: [{state: absent, ip-from: 192.0.2.1, route-table: 500}]",
    );
    let mut rule = kernel_rule("192.0.2.1", 500);
    assert!(kernel_rule_is_absent(&rule, &merged));
    rule.flags.push(RouteRuleFlag::Invert);
    assert!(!kernel_rule_is_absent(&rule, &merged));
}

#[test]
fn test_kernel_route_rule_kernel_protocol_never_absent() {
    let merged = merged_rules("config: [{state: absent}]");
    let mut rule = kernel_rule("192.0.2.1", 500);
    assert!(kernel_rule_is_absent(&rule, &merged));
    rule.protocol = Some(RouteProtocol::Kernel);
    assert!(!kernel_rule_is_absent(&rule, &merged));
}

#[test]
fn test_kernel_route_rule_zero_mark_with_mask() {
    let mut rule = kernel_rule("192.0.2.1", 500);
    rule.fw_mask = Some(255);
    let merged = merged_rules(
        "config: [{route-table: 500, fwmark: 0, fwmask: 255, state: absent}]",
    );
    assert!(kernel_rule_is_absent(&rule, &merged));
    rule.fw_mark = Some(1);
    assert!(!kernel_rule_is_absent(&rule, &merged));
}

#[test]
fn test_kernel_route_rule_absent_without_query_record() {
    let mut rule = kernel_rule("192.0.2.1", 500);
    rule.tun_id = Some(0x1_0000_0001);
    let desired: RouteRules =
        serde_yaml::from_str("config: [{route-table: 500, state: absent}]")
            .unwrap();
    let merged = MergedRouteRules::new(desired, RouteRules::default()).unwrap();
    assert!(merged.for_apply.is_empty());
    assert!(kernel_rule_is_absent(&rule, &merged));
}

#[test]
fn test_kernel_route_rule_absent_respects_ignored_interface() {
    let mut rule = kernel_rule("192.0.2.1", 500);
    rule.iif = Some("eth1".into());
    rule.tun_id = Some(0x1_0000_0001);
    let mut merged =
        merged_rules("config: [{route-table: 500, state: absent}]");
    assert!(kernel_rule_is_absent(&rule, &merged));
    merged.remove_rules_to_ignored_ifaces(&[(
        "eth1".into(),
        crate::InterfaceType::Ethernet,
    )]);
    assert!(!kernel_rule_is_absent(&rule, &merged));
    merged.remove_rules_to_ignored_ifaces(&[(
        "eth1".into(),
        crate::InterfaceType::OvsBridge,
    )]);
    assert!(kernel_rule_is_absent(&rule, &merged));
}

#[test]
fn test_kernel_route_rule_exact_priority_zero() {
    let merged = merged_rules(
        "config: [{route-table: 500, priority: 0, state: absent}]",
    );
    let mut rule = kernel_rule("192.0.2.1", 500);
    assert!(!kernel_rule_is_absent(&rule, &merged));
    rule.priority = Some(0);
    assert!(kernel_rule_is_absent(&rule, &merged));
}
