// SPDX-License-Identifier: Apache-2.0

use nispor::{
    AddressFamily, RouteProtocol, RouteRule, RouteRuleFlag, RuleAction,
};

use crate::{
    ErrorKind, MergedRouteRules, RouteRuleEntry, RouteRules,
    nispor::{
        get_route_rules, get_route_rules_for_apply, kernel_rule_is_absent,
        plan_route_rule_removals,
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
        assert!(!queried.config.as_ref().unwrap()[0].apply_ignored);
        assert!(queried.config.as_ref().unwrap()[1].apply_ignored);
        assert!(queried.config.as_ref().unwrap()[2].apply_ignored);
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
        get_route_rules(&[selected, dynamic.clone(), inverted.clone()], false),
    )
    .unwrap();
    assert_eq!(merged.for_apply.len(), 1);
    assert!(merged.for_apply[0].is_absent());
    let remaining = [dynamic, inverted];
    assert_eq!(get_route_rules(&remaining, false).config.unwrap().len(), 2);
    merged
        .verify(&get_route_rules(&remaining, false), &[])
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
    let current = get_route_rules(&[dynamic.clone(), inverted.clone()], false);
    let merged = MergedRouteRules::new(desired, current.clone()).unwrap();
    assert_eq!(merged.for_apply.len(), 1);
    assert!(!merged.for_apply[0].is_absent());
    assert_eq!(
        merged.verify(&current, &[]).unwrap_err().kind(),
        ErrorKind::VerificationError
    );
    merged
        .verify(&get_route_rules(&[selected, dynamic, inverted], false), &[])
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
fn test_ignored_kernel_rules_reserve_priorities_without_identity_reuse() {
    for source in ["192.0.2.1", "2001:db8::1"] {
        for inverted in [false, true] {
            let mut rule = kernel_rule(source, 500);
            rule.priority = Some(30005);
            if inverted {
                rule.flags.push(RouteRuleFlag::Invert);
            } else {
                rule.protocol = Some(RouteProtocol::KeepAlived);
            }
            let desired = serde_yaml::from_str(&format!(
                "config: [{{ip-from: '{source}', route-table: 500}}]"
            ))
            .unwrap();
            let merged =
                MergedRouteRules::new(desired, get_route_rules(&[rule], false))
                    .unwrap();
            assert_eq!(merged.for_apply.len(), 1);
            assert_eq!(merged.for_apply[0].priority, Some(30006));
        }
    }
}

#[test]
fn test_default_priority_excludes_kernel_and_removed_rules() {
    let mut kernel = kernel_rule("0.0.0.0", 254);
    kernel.priority = Some(32766);
    kernel.protocol = Some(RouteProtocol::Kernel);
    let mut removed = kernel_rule("192.0.2.1", 500);
    removed.priority = Some(40000);
    for rules in [vec![kernel.clone()], vec![kernel, removed]] {
        let desired = serde_yaml::from_str(
            "config: [{state: absent, route-table: 500}, {ip-from: \
             '192.0.2.2', route-table: 500}]",
        )
        .unwrap();
        let merged =
            MergedRouteRules::new(desired, get_route_rules(&rules, false))
                .unwrap();
        assert_eq!(merged.for_apply[0].priority, Some(30000));
    }
}

#[test]
fn test_rule_diff_ignores_inverted_current_entries() {
    let ordinary = kernel_rule("192.0.2.1", 500);
    let mut inverted = ordinary.clone();
    inverted.flags.push(RouteRuleFlag::Invert);
    let desired: RouteRules = serde_yaml::from_str(
        "config: [{ip-from: '192.0.2.1', priority: 200, route-table: 500}]",
    )
    .unwrap();
    let current = get_route_rules(std::slice::from_ref(&inverted), true);
    let merged =
        MergedRouteRules::new(desired.clone(), current.clone()).unwrap();
    assert_eq!(merged.gen_diff().config.unwrap().len(), 1);
    assert!(merged.verify(&current, &[]).is_err());
    let absent =
        serde_yaml::from_str("config: [{state: absent, route-table: 500}]")
            .unwrap();
    let merged = MergedRouteRules::new(absent, current).unwrap();
    assert!(merged.gen_diff().is_empty());
    for rules in [[ordinary.clone(), inverted.clone()], [inverted, ordinary]] {
        let current = get_route_rules(&rules, true);
        let merged =
            MergedRouteRules::new(desired.clone(), current.clone()).unwrap();
        assert!(merged.gen_diff().is_empty());
        merged.verify(&current, &[]).unwrap();
    }
}

#[test]
fn test_rule_eligibility_is_private_query_metadata() {
    let mut inverted = kernel_rule("192.0.2.1", 500);
    inverted.flags.push(RouteRuleFlag::Invert);
    let current = get_route_rules(&[inverted], true);
    let rule = &current.config.as_ref().unwrap()[0];
    assert!(rule.apply_ignored);
    let value = serde_json::to_value(rule).unwrap();
    assert!(!value.as_object().unwrap().contains_key("apply-ignored"));
    assert!(!value.as_object().unwrap().contains_key("apply_ignored"));
    let restored: RouteRuleEntry =
        serde_json::from_value(value.clone()).unwrap();
    assert!(!restored.apply_ignored);
    assert_eq!(&restored, rule);
    let mut invalid = value;
    invalid["apply-ignored"] = true.into();
    assert!(serde_json::from_value::<RouteRuleEntry>(invalid).is_err());
    let from_query =
        MergedRouteRules::new(current.clone(), RouteRules::new()).unwrap();
    let deserialized: RouteRules =
        serde_json::from_value(serde_json::to_value(&current).unwrap())
            .unwrap();
    let from_json =
        MergedRouteRules::new(deserialized, RouteRules::new()).unwrap();
    assert!(!from_query.desired.config.as_ref().unwrap()[0].apply_ignored);
    assert!(!from_query.for_apply[0].apply_ignored);
    assert_eq!(from_query, from_json);
}

#[test]
#[cfg(feature = "gen_revert")]
fn test_rule_revert_does_not_recreate_preserved_rules() {
    let ordinary = kernel_rule("192.0.2.1", 500);
    let mut inverted = kernel_rule("192.0.2.2", 500);
    inverted.flags.push(RouteRuleFlag::Invert);
    let desired =
        serde_yaml::from_str("config: [{state: absent, route-table: 500}]")
            .unwrap();
    let merged = MergedRouteRules::new(
        desired,
        get_route_rules(&[ordinary.clone(), inverted], true),
    )
    .unwrap();
    assert_eq!(merged.generate_revert(), get_route_rules(&[ordinary], true));
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
    rule.tun_id = Some(u64::MAX);
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
    rule.tun_id = Some(u64::MAX);
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

#[test]
fn test_rule_delete_plan_preserves_protocol_twins() {
    let merged = merged_rules("config: [{state: absent, route-table: 500}]");
    let mut selected = kernel_rule("192.0.2.1", 500);
    selected.protocol = Some(RouteProtocol::Static);
    let mut retained = selected.clone();
    retained.protocol = Some(RouteProtocol::KeepAlived);
    let plan =
        plan_route_rule_removals(&merged, &[retained, selected], &[]).unwrap();
    assert_eq!(plan.len(), 1);
    assert_eq!(plan[0].protocol, Some(RouteProtocol::Static));
}

#[test]
fn test_rule_delete_plan_keeps_unmatched_tables_and_duplicate_counts() {
    let merged = merged_rules("config: [{state: absent, route-table: 500}]");
    let selected = kernel_rule("192.0.2.1", 500);
    let retained = kernel_rule("192.0.2.1", 501);
    let plan = plan_route_rule_removals(
        &merged,
        &[retained.clone(), selected.clone(), selected, retained],
        &[],
    )
    .unwrap();
    assert_eq!(plan.len(), 2);
    assert!(plan.iter().all(|r| r.table == Some(500)));
}

#[test]
fn test_rule_delete_plan_rejects_whole_ambiguous_batch() {
    let merged = merged_rules("config: [{state: absent, route-table: 500}]");
    let first = kernel_rule("192.0.2.2", 500);
    let selected = kernel_rule("192.0.2.1", 500);
    let mut inverted = selected.clone();
    inverted.flags.push(RouteRuleFlag::Invert);
    let err =
        plan_route_rule_removals(&merged, &[first, inverted, selected], &[])
            .unwrap_err();
    assert_eq!(err.kind(), ErrorKind::NotSupportedError);
    assert!(err.msg().contains("No external rules were deleted"));
}

#[test]
fn test_rule_delete_plan_preserves_dump_order() {
    let merged = merged_rules("config: [{state: absent, route-table: 500}]");
    let specific = kernel_rule("192.0.2.2", 500);
    let mut generic = kernel_rule("192.0.2.1", 500);
    generic.src = None;
    let rules = [specific.clone(), generic.clone(), specific.clone()];
    let plan = plan_route_rule_removals(&merged, &rules, &[]).unwrap();
    assert_eq!(
        plan.iter().map(|r| r.src.clone()).collect::<Vec<_>>(),
        vec![specific.src.clone(), generic.src, specific.src]
    );
}

#[test]
fn test_rule_delete_plan_rejects_later_wildcard_neighbors() {
    for tableless in [false, true] {
        let merged = merged_rules("config: [{state: absent}]");
        let mut selected = kernel_rule("192.0.2.1", 500);
        let mut retained = selected.clone();
        retained.flags.push(RouteRuleFlag::Invert);
        if tableless {
            selected.action = RuleAction::Blackhole;
            selected.table = None;
            retained.action = RuleAction::Blackhole;
        } else {
            retained.suppress_prefix_len = Some(0);
        }
        let err = plan_route_rule_removals(&merged, &[selected, retained], &[])
            .unwrap_err();
        assert_eq!(err.kind(), ErrorKind::NotSupportedError);
    }
}

#[test]
fn test_rule_delete_plan_zero_mark_cannot_remove_marked_neighbor() {
    let merged = merged_rules(
        "config: [{state: absent, route-table: 500, fwmark: 0, fwmask: 255}]",
    );
    let mut selected = kernel_rule("192.0.2.1", 500);
    selected.fw_mask = Some(255);
    let mut retained = selected.clone();
    retained.fw_mark = Some(1);
    assert!(
        plan_route_rule_removals(&merged, &[retained, selected.clone()], &[],)
            .is_err()
    );
    let plan = plan_route_rule_removals(&merged, &[selected], &[]).unwrap();
    assert_eq!(plan[0].fw_mark, Some(0));
    assert_eq!(plan[0].fw_mask, Some(255));
}

#[test]
fn test_rule_delete_plan_nonzero_mark_separates_neighbor() {
    let merged = merged_rules(
        "config: [{state: absent, route-table: 500, fwmark: 1, fwmask: 255}]",
    );
    let mut retained = kernel_rule("192.0.2.1", 500);
    retained.fw_mask = Some(255);
    let mut selected = retained.clone();
    selected.fw_mark = Some(1);
    let plan =
        plan_route_rule_removals(&merged, &[retained, selected], &[]).unwrap();
    assert_eq!(plan.len(), 1);
    assert_eq!(plan[0].fw_mark, Some(1));
}

#[test]
fn test_rule_delete_plan_missing_selectors_cannot_target_ignored_interface() {
    let mut merged =
        merged_rules("config: [{state: absent, route-table: 500}]");
    merged.ignored_ifaces.push("eth1".into());
    let selected = kernel_rule("192.0.2.1", 500);
    let mut ignored = selected.clone();
    ignored.iif = Some("eth1".into());
    assert!(
        plan_route_rule_removals(&merged, &[ignored, selected], &[]).is_err()
    );
}

#[test]
fn test_rule_delete_plan_unspecified_protocol_cannot_target_dynamic_rule() {
    let merged = merged_rules("config: [{state: absent, route-table: 500}]");
    let mut selected = kernel_rule("192.0.2.1", 500);
    selected.protocol = Some(RouteProtocol::Unspec);
    let mut retained = selected.clone();
    retained.protocol = Some(RouteProtocol::Dhcp);
    assert!(
        plan_route_rule_removals(&merged, &[retained, selected], &[]).is_err()
    );
}

#[test]
fn test_rule_delete_plan_preserves_desired_present_and_profile_rules() {
    let selected = kernel_rule("192.0.2.1", 500);
    let retained = kernel_rule("192.0.2.2", 500);
    let desired = merged_rules(
        r"config:
        - state: absent
          route-table: 500
        - ip-from: 192.0.2.2/32
          priority: 200
          route-table: 500",
    );
    let plan = plan_route_rule_removals(
        &desired,
        &[selected.clone(), retained.clone()],
        &[],
    )
    .unwrap();
    assert_eq!(plan.len(), 1);
    assert_eq!(plan[0].src.as_deref(), Some("192.0.2.1/32"));

    let absent = merged_rules("config: [{state: absent, route-table: 500}]");
    let protected = get_route_rules_for_apply(std::slice::from_ref(&retained))
        .config
        .unwrap();
    let plan =
        plan_route_rule_removals(&absent, &[selected, retained], &protected)
            .unwrap();
    assert_eq!(plan.len(), 1);
    assert_eq!(plan[0].src.as_deref(), Some("192.0.2.1/32"));
}

#[test]
fn test_rule_delete_plan_configured_from_all_is_not_a_wildcard() {
    for (source, family) in [("192.0.2.1", "ipv4"), ("2001:db8::1", "ipv6")] {
        let selected = kernel_rule(source, 500);
        let mut retained = selected.clone();
        retained.src = None;
        let protected =
            get_route_rules_for_apply(std::slice::from_ref(&retained))
                .config
                .unwrap();
        let desired = merged_rules(&format!(
            "config: [{{state: absent, ip-from: '{source}', route-table: \
             500}}]"
        ));
        let rules = [retained, selected];
        let plan =
            plan_route_rule_removals(&desired, &rules, &protected).unwrap();
        assert_eq!(plan.len(), 1);
        assert_eq!(plan[0].src, rules[1].src);

        let desired = merged_rules(&format!(
            "config: [{{state: absent, route-table: 500}}, {{family: \
             {family}, priority: 200, route-table: 500}}]"
        ));
        let plan = plan_route_rule_removals(&desired, &rules, &[]).unwrap();
        assert_eq!(plan.len(), 1);
        assert_eq!(plan[0].src, rules[1].src);
    }
}

#[test]
fn test_rule_delete_plan_configured_selectors_are_concrete() {
    let desired = merged_rules("config: [{state: absent, route-table: 500}]");
    let retained = kernel_rule("192.0.2.1", 500);
    let protected = get_route_rules_for_apply(std::slice::from_ref(&retained))
        .config
        .unwrap();
    let mut candidates = vec![retained.clone(); 5];
    candidates[0].iif = Some("eth1".into());
    candidates[1].fw_mark = Some(1);
    candidates[1].fw_mask = Some(u32::MAX);
    candidates[2].fw_mask = Some(255);
    candidates[3].suppress_prefix_len = Some(0);
    candidates[4].action = RuleAction::Blackhole;
    for selected in candidates {
        let plan = plan_route_rule_removals(
            &desired,
            &[retained.clone(), selected],
            &protected,
        )
        .unwrap();
        assert_eq!(plan.len(), 1);
    }
}

#[test]
fn test_rule_delete_plan_normalizes_configured_zero_selectors() {
    let desired = merged_rules("config: [{state: absent, route-table: 500}]");
    for (source, all) in [("192.0.2.1", "0.0.0.0/0"), ("2001:db8::1", "::/0")] {
        let mut retained = kernel_rule(source, 500);
        retained.src = None;
        retained.priority = None;
        let mut protected =
            get_route_rules_for_apply(std::slice::from_ref(&retained))
                .config
                .unwrap();
        protected[0].ip_from = Some(all.into());
        protected[0].ip_to = Some(String::new());
        protected[0].priority = Some(0);
        protected[0].iif = Some(String::new());
        protected[0].fwmark = Some(0);
        protected[0].fwmask = Some(0);
        protected[0].suppress_prefix_length = Some(u32::MAX);
        assert!(
            plan_route_rule_removals(&desired, &[retained], &protected)
                .unwrap()
                .is_empty()
        );
    }
}

#[test]
fn test_rule_delete_plan_preserves_configured_zero_mask() {
    let desired = merged_rules("config: [{state: absent, route-table: 500}]");
    let mut retained = kernel_rule("192.0.2.1", 500);
    retained.fw_mark = Some(1);
    retained.fw_mask = Some(0);
    let mut protected =
        get_route_rules_for_apply(std::slice::from_ref(&retained))
            .config
            .unwrap();
    protected[0].fwmask = None;
    let mut selected = retained.clone();
    selected.fw_mask = Some(u32::MAX);
    let plan =
        plan_route_rule_removals(&desired, &[retained, selected], &protected)
            .unwrap();
    assert_eq!(plan.len(), 1);
    assert_eq!(plan[0].fw_mask, Some(u32::MAX));
}

#[test]
fn test_rule_delete_plan_preserves_configured_full_mask() {
    let desired = merged_rules("config: [{state: absent, route-table: 500}]");
    let mut retained = kernel_rule("192.0.2.1", 500);
    retained.fw_mark = Some(1);
    retained.fw_mask = Some(u32::MAX);
    let protected = get_route_rules_for_apply(std::slice::from_ref(&retained))
        .config
        .unwrap();
    assert!(
        plan_route_rule_removals(&desired, &[retained], &protected)
            .unwrap()
            .is_empty()
    );
}

#[test]
fn test_rule_delete_plan_normalizes_desired_default_table() {
    let desired = merged_rules(
        "config: [{state: absent}, {family: ipv4, priority: 200, route-table: \
         0}]",
    );
    let mut retained = kernel_rule("192.0.2.1", 254);
    retained.src = None;
    assert!(
        plan_route_rule_removals(&desired, &[retained], &[])
            .unwrap()
            .is_empty()
    );
}

#[test]
fn test_rule_delete_plan_preserves_profile_and_desired_action_tables() {
    for (action, name) in [
        (RuleAction::Blackhole, "blackhole"),
        (RuleAction::Unreachable, "unreachable"),
        (RuleAction::Prohibit, "prohibit"),
    ] {
        let mut retained = kernel_rule("192.0.2.1", 254);
        retained.action = action;
        let desired = merged_rules(&format!(
            "config: [{{state: absent, action: {name}}}, {{ip-from: \
             192.0.2.1/32, priority: 200, action: {name}}}]"
        ));
        assert!(
            plan_route_rule_removals(
                &desired,
                std::slice::from_ref(&retained),
                &[],
            )
            .unwrap()
            .is_empty()
        );

        retained.table = None;
        let protected =
            get_route_rules_for_apply(std::slice::from_ref(&retained))
                .config
                .unwrap();
        let desired = merged_rules(&format!(
            "config: [{{state: absent, action: {name}}}]"
        ));
        assert!(
            plan_route_rule_removals(&desired, &[retained], &protected)
                .unwrap()
                .is_empty()
        );
    }
}

#[test]
fn test_rule_delete_plan_auto_priority_protects_present_rule() {
    let desired = merged_rules(
        r"config:
        - state: absent
          route-table: 500
        - ip-from: 192.0.2.2/32
          route-table: 500",
    );
    let priority = desired
        .for_apply
        .iter()
        .find(|r| !r.is_absent())
        .unwrap()
        .priority
        .unwrap() as u32;
    let mut retained = kernel_rule("192.0.2.2", 500);
    retained.priority = Some(priority);
    assert!(
        plan_route_rule_removals(&desired, &[retained], &[])
            .unwrap()
            .is_empty()
    );
}

#[test]
fn test_rule_delete_plan_normalizes_missing_priority_to_zero() {
    let desired = merged_rules(
        "config: [{state: absent, priority: 0, route-table: 500}]",
    );
    let mut selected = kernel_rule("192.0.2.1", 500);
    selected.priority = None;
    let plan = plan_route_rule_removals(&desired, &[selected], &[]).unwrap();
    assert_eq!(plan.len(), 1);
    assert_eq!(plan[0].priority, 0);
}

#[test]
fn test_rule_delete_plan_validates_all_requests_before_mutation() {
    let desired = merged_rules("config: [{state: absent}]");
    let first = kernel_rule("192.0.2.1", 500);
    let mut malformed = first.clone();
    malformed.table = None;
    let err = plan_route_rule_removals(&desired, &[first, malformed], &[])
        .unwrap_err();
    assert_eq!(err.kind(), ErrorKind::NotSupportedError);
}

#[test]
fn test_rule_delete_plan_rejects_unsupported_l3mdev_before_mutation() {
    let desired = merged_rules("config: [{state: absent}]");
    let first = kernel_rule("192.0.2.1", 500);
    let mut l3mdev = kernel_rule("0.0.0.0", 500);
    l3mdev.src = None;
    l3mdev.table = None;
    l3mdev.l3mdev = Some(true);
    l3mdev.protocol = Some(RouteProtocol::Unspec);
    let err =
        plan_route_rule_removals(&desired, &[first, l3mdev], &[]).unwrap_err();
    assert_eq!(err.kind(), ErrorKind::NotSupportedError);
    assert!(err.msg().contains("No external rules were deleted"));
}

#[test]
fn test_rule_delete_plan_matches_automatic_suppress_rules_outside_profiles() {
    for source in ["0.0.0.0", "::"] {
        let mut suppress = kernel_rule(source, 254);
        suppress.src = None;
        suppress.priority = Some(31000);
        suppress.protocol = Some(RouteProtocol::Unspec);
        suppress.suppress_prefix_len = Some(0);
        let mut inverted = suppress.clone();
        inverted.priority = Some(31001);
        inverted.table = Some(51820);
        inverted.suppress_prefix_len = None;
        inverted.fw_mark = Some(51820);
        inverted.fw_mask = Some(u32::MAX);
        inverted.flags.push(RouteRuleFlag::Invert);
        let desired =
            merged_rules("config: [{state: absent, route-table: 254}]");
        let plan =
            plan_route_rule_removals(&desired, &[suppress, inverted], &[])
                .unwrap();
        assert_eq!(plan.len(), 1);
        assert_eq!(plan[0].priority, 31000);
        assert_eq!(plan[0].suppress_prefix_len, Some(0));
    }
}

#[test]
#[ignore = "requires unshare with user and network namespace support"]
fn test_kernel_rule_deletion_preserves_protected_records() {
    use std::process::Command;

    use crate::{NetworkState, nispor::remove_external_route_rules};

    let namespace = std::fs::read_link("/proc/self/ns/net").unwrap();
    if let Some(parent) = std::env::var_os("NMSTATE_TEST_PARENT_NETNS") {
        assert_ne!(namespace, std::path::PathBuf::from(parent));
    } else {
        let status = Command::new("unshare")
            .args(["--user", "--map-root-user", "--net"])
            .arg(std::env::current_exe().unwrap())
            .args([
                "--ignored",
                "--exact",
                "unit_tests::kernel_route_rule::test_kernel_rule_deletion_preserves_protected_records",
            ])
            .env("NMSTATE_TEST_PARENT_NETNS", namespace)
            .status()
            .unwrap();
        assert!(status.success());
        return;
    }
    fn ip(args: &[&str]) {
        let output = Command::new("ip").args(args).output().unwrap();
        assert!(
            output.status.success(),
            "ip {args:?}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }
    async fn rules() -> Vec<nispor::RouteRule> {
        let mut filter = nispor::NetStateFilter::minimum();
        filter.route_rule = Some(Default::default());
        nispor::NetState::retrieve_with_filter_async(&filter)
            .await
            .unwrap()
            .rules
    }
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_io()
        .enable_time()
        .build()
        .unwrap();
    rt.block_on(async {
        let initial = rules().await;
        for family in ["-4", "-6"] {
            for priority in ["0", "1000"] {
                for protocol in ["18", "4"] {
                    ip(&[
                        family, "rule", "add", "priority", priority, "table",
                        "500", "protocol", protocol,
                    ]);
                }
                ip(&[
                    family, "rule", "add", "priority", priority, "table",
                    "501", "protocol", "4",
                ]);
            }
            let source = if family == "-4" {
                "192.0.2.1/32"
            } else {
                "2001:db8::1/128"
            };
            ip(&[
                family, "rule", "add", "from", source, "priority", "4000",
                "table", "502", "protocol", "18",
            ]);
            for (priority, action) in [
                ("3000", "blackhole"),
                ("3001", "unreachable"),
                ("3002", "prohibit"),
            ] {
                ip(&[
                    family, "rule", "add", "from", source, "priority",
                    priority, "protocol", "4", action,
                ]);
            }
        }
        let before_reapply = rules().await;
        let mut current = NetworkState::new();
        current.set_kernel_only(true);
        current.retrieve_async().await.unwrap();
        let dynamic_rules: Vec<_> = current
            .rules
            .config
            .unwrap()
            .into_iter()
            .filter(|rule| rule.table_id == Some(502))
            .collect();
        assert_eq!(dynamic_rules.len(), 2);
        let mut desired = NetworkState::new();
        desired.set_kernel_only(true);
        desired.rules.config = Some(dynamic_rules);
        desired.apply_async().await.unwrap();
        assert_eq!(rules().await, before_reapply);

        let desired = merged_rules(
            "config: [{state: absent, route-table: 500}, {state: absent, \
             action: blackhole}, {state: absent, action: unreachable}, \
             {state: absent, action: prohibit}]",
        );
        let before = rules().await;
        let expected: Vec<_> = before
            .iter()
            .filter(|rule| {
                !((rule.table == Some(500)
                    || matches!(
                        rule.action,
                        RuleAction::Blackhole
                            | RuleAction::Unreachable
                            | RuleAction::Prohibit
                    ))
                    && rule.protocol == Some(RouteProtocol::Static))
            })
            .cloned()
            .collect();
        remove_external_route_rules(&desired, &NetworkState::new())
            .await
            .unwrap();
        assert_eq!(rules().await, expected);
        remove_external_route_rules(&desired, &NetworkState::new())
            .await
            .unwrap();
        assert_eq!(rules().await, expected);

        ip(&[
            "-4", "rule", "add", "priority", "2000", "table", "500",
            "protocol", "4",
        ]);
        ip(&[
            "-4", "rule", "add", "priority", "2001", "table", "500",
            "protocol", "4",
        ]);
        ip(&[
            "-4",
            "rule",
            "add",
            "not",
            "from",
            "192.0.2.1/32",
            "priority",
            "2001",
            "table",
            "500",
            "protocol",
            "4",
        ]);
        let before_ambiguous = rules().await;
        let error = remove_external_route_rules(&desired, &NetworkState::new())
            .await
            .unwrap_err();
        assert_eq!(error.kind(), ErrorKind::NotSupportedError);
        assert_eq!(rules().await, before_ambiguous);
        assert!(initial.iter().all(|rule| before_ambiguous.contains(rule)));
    });
}
