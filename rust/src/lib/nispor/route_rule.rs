// SPDX-License-Identifier: Apache-2.0

use log::warn;

use crate::{
    AddressFamily, ErrorKind, MergedRouteRules, NetworkState, NmstateError,
    RouteRuleAction, RouteRuleEntry, RouteRules, rollback::RouteRuleRemoval,
};

pub(crate) async fn route_rule_worker_needed(
    merged_rules: &MergedRouteRules,
    current: &NetworkState,
) -> Result<bool, NmstateError> {
    if !merged_rules
        .desired
        .config
        .iter()
        .flatten()
        .any(|r| r.is_absent())
    {
        return Ok(false);
    }
    let mut owned = current
        .interfaces
        .kernel_ifaces
        .values()
        .chain(current.interfaces.user_ifaces.values())
        .flat_map(|iface| {
            let base = iface.base_iface();
            base.ipv4
                .as_ref()
                .and_then(|ip| ip.rules.as_ref())
                .into_iter()
                .flatten()
                .chain(
                    base.ipv6
                        .as_ref()
                        .and_then(|ip| ip.rules.as_ref())
                        .into_iter()
                        .flatten(),
                )
        })
        .cloned()
        .collect::<Vec<_>>();
    let plan = RouteRuleRemoval::prepare_with_projection(|rule, complete| {
        if !kernel_rule_is_absent(rule, merged_rules) {
            return false;
        }
        !take_profile_rule(rule, complete, &mut owned)
    })
    .await
    .map_err(|e| NmstateError::new(ErrorKind::PluginFailure, e.to_string()))?;
    Ok(!plan.is_empty())
}

fn take_profile_rule(
    rule: &nispor::RouteRule,
    projection_complete: bool,
    owned: &mut Vec<RouteRuleEntry>,
) -> bool {
    fn normalize(entry: &RouteRuleEntry) -> Option<RouteRuleEntry> {
        let mut entry = entry.clone();
        if entry.state.is_some() || entry.priority.is_none_or(|p| p < 0) {
            return None;
        }
        // NM omits zero-valued mark and mask fields independently on D-Bus.
        entry.fwmark = Some(entry.fwmark.unwrap_or(0));
        entry.fwmask = Some(entry.fwmask.unwrap_or(0));
        if entry.table_id == Some(RouteRuleEntry::USE_DEFAULT_ROUTE_TABLE) {
            entry.table_id = Some(RouteRuleEntry::DEFAULR_ROUTE_TABLE_ID);
        }
        entry.sanitize().ok()?;
        for network in [&mut entry.ip_from, &mut entry.ip_to] {
            if matches!(network.as_deref(), Some("0.0.0.0/0" | "::/0")) {
                *network = None;
            }
        }
        if entry.iif.as_deref() == Some("") {
            entry.iif = None;
        }
        Some(entry)
    }

    fn same(left: &RouteRuleEntry, right: &RouteRuleEntry) -> bool {
        left.family == right.family
            && left.priority == right.priority
            && left.table_id == right.table_id
            && left.ip_from == right.ip_from
            && left.ip_to == right.ip_to
            && left.fwmark == right.fwmark
            && left.fwmask == right.fwmask
            && left.action == right.action
            && left.iif == right.iif
            && left.suppress_prefix_length == right.suppress_prefix_length
    }

    if !projection_complete
        || !rule.flags.is_empty()
        || !matches!(
            rule.protocol,
            None | Some(
                nispor::RouteProtocol::Unspec | nispor::RouteProtocol::Static
            )
        )
        || rule.tos != 0
        || rule.oif.is_some()
        || rule.goto.is_some()
        || rule.mask.is_some()
        || rule.realm.is_some()
        || rule.tun_id.is_some()
        || rule.suppress_ifgroup.is_some()
        || rule.ip_proto.is_some()
        || rule.src_port_range.is_some()
        || rule.dst_port_range.is_some()
        || rule.l3mdev == Some(true)
        || (rule.action == nispor::RuleAction::Table
            && rule.table.is_none_or(|table| table == 0))
    {
        return false;
    }
    let Some(projected) = get_route_rules_for_apply(std::slice::from_ref(rule))
        .config
        .and_then(|rules| rules.into_iter().next())
        .and_then(|rule| normalize(&rule))
    else {
        return false;
    };
    let mut found = false;
    // NM shares identical rules across profiles. Multiple profile references
    // cannot establish ownership of multiple identical kernel records.
    owned.retain(|entry| {
        if normalize(entry).is_some_and(|entry| same(&entry, &projected)) {
            found = true;
            false
        } else {
            true
        }
    });
    found
}

pub(crate) fn kernel_rule_is_absent(
    rule: &nispor::RouteRule,
    merged_rules: &MergedRouteRules,
) -> bool {
    let rules = get_route_rules_for_apply(std::slice::from_ref(rule));
    rules.config.unwrap_or_default().iter().any(|current| {
        if current
            .iif
            .as_ref()
            .is_some_and(|name| merged_rules.ignored_ifaces.contains(name))
        {
            return false;
        }
        merged_rules
            .desired
            .config
            .iter()
            .flatten()
            .any(|rule| rule.is_absent() && rule.is_match(current))
    })
}

// Due to a bug in NetworkManager all route rules added using NetworkManager are
// using RTM_PROTOCOL Unspec. Therefore, we need to support it until it is
// fixed.
const SUPPORTED_STATIC_ROUTE_PROTOCOL: [nispor::RouteProtocol; 3] = [
    nispor::RouteProtocol::Boot,
    nispor::RouteProtocol::Static,
    nispor::RouteProtocol::Unspec,
];

const SUPPORTED_ROUTE_PROTOCOL: [nispor::RouteProtocol; 8] = [
    nispor::RouteProtocol::Boot,
    nispor::RouteProtocol::Static,
    nispor::RouteProtocol::Ra,
    nispor::RouteProtocol::Dhcp,
    nispor::RouteProtocol::Mrouted,
    nispor::RouteProtocol::KeepAlived,
    nispor::RouteProtocol::Babel,
    nispor::RouteProtocol::Unspec,
];

pub(crate) fn get_route_rules(
    np_rules: &[nispor::RouteRule],
    running_config_only: bool,
) -> RouteRules {
    get_route_rules_from_iter(np_rules.iter(), running_config_only)
}

pub(crate) fn get_route_rules_for_apply(
    np_rules: &[nispor::RouteRule],
) -> RouteRules {
    // Dynamic rules belong to their owners, and nmstate cannot express
    // inverted selectors. Neither should enter absent-rule verification.
    get_route_rules_from_iter(
        np_rules.iter().filter(|rule| {
            !rule.flags.contains(&nispor::RouteRuleFlag::Invert)
        }),
        true,
    )
}

fn get_route_rules_from_iter<'a>(
    np_rules: impl Iterator<Item = &'a nispor::RouteRule>,
    running_config_only: bool,
) -> RouteRules {
    let mut ret = RouteRules::new();

    let mut rules = Vec::new();
    let protocols = if running_config_only {
        SUPPORTED_STATIC_ROUTE_PROTOCOL.as_slice()
    } else {
        SUPPORTED_ROUTE_PROTOCOL.as_slice()
    };

    for np_rule in np_rules {
        let mut rule = RouteRuleEntry::new();
        // We only support route rules with 'table' action
        match np_rule.action {
            nispor::RuleAction::Table => (),
            nispor::RuleAction::Blackhole => {
                rule.action = Some(RouteRuleAction::Blackhole)
            }
            nispor::RuleAction::Unreachable => {
                rule.action = Some(RouteRuleAction::Unreachable)
            }
            nispor::RuleAction::Prohibit => {
                rule.action = Some(RouteRuleAction::Prohibit)
            }
            _ => {
                log::debug!("Got unsupported route rule {np_rule:?}");
                continue;
            }
        }
        // Filter out the routes with protocols that we do not support
        if let Some(rule_protocol) = np_rule.protocol.as_ref()
            && !protocols.contains(rule_protocol)
        {
            continue;
        }
        rule.iif.clone_from(&np_rule.iif);
        rule.ip_to.clone_from(&np_rule.dst);
        rule.ip_from.clone_from(&np_rule.src);
        rule.table_id = np_rule.table;
        rule.priority = np_rule.priority.map(i64::from);
        rule.fwmark = np_rule.fw_mark.or(np_rule.fw_mask.map(|_| 0));
        rule.fwmask = np_rule.fw_mask;
        rule.suppress_prefix_length = np_rule.suppress_prefix_len;
        rule.family = match np_rule.address_family {
            nispor::AddressFamily::Ipv4 => Some(AddressFamily::IPv4),
            nispor::AddressFamily::Ipv6 => Some(AddressFamily::IPv6),
            _ => {
                warn!(
                    "Unsupported route rule family {:?}",
                    np_rule.address_family
                );
                None
            }
        };
        rules.push(rule);
    }
    ret.config = Some(rules);

    ret
}

#[cfg(test)]
mod tests {
    use super::*;

    fn profile_rule() -> RouteRuleEntry {
        let mut rule = RouteRuleEntry::new();
        rule.family = Some(AddressFamily::IPv4);
        rule.priority = Some(1000);
        rule.table_id = Some(500);
        rule
    }

    fn kernel_rule() -> nispor::RouteRule {
        let mut rule = nispor::RouteRule::default();
        rule.action = nispor::RuleAction::Table;
        rule.address_family = nispor::AddressFamily::Ipv4;
        rule.priority = Some(1000);
        rule.table = Some(500);
        rule.protocol = Some(nispor::RouteProtocol::Unspec);
        rule
    }

    #[test]
    fn profile_ownership_consumes_one_kernel_record_per_unique_profile_rule() {
        let mut owned = vec![profile_rule(), profile_rule()];
        assert!(take_profile_rule(&kernel_rule(), true, &mut owned));
        assert!(owned.is_empty());
        assert!(!take_profile_rule(&kernel_rule(), true, &mut owned));
    }

    #[test]
    fn opaque_rules_do_not_consume_matching_profile_ownership() {
        let mut owned = vec![profile_rule()];
        assert!(!take_profile_rule(&kernel_rule(), false, &mut owned));
        assert_eq!(owned.len(), 1);
        assert!(take_profile_rule(&kernel_rule(), true, &mut owned));
    }

    #[test]
    fn profile_ownership_accepts_nm_static_protocol_only_for_complete_matches()
    {
        for (family, np_family, source) in [
            (
                AddressFamily::IPv4,
                nispor::AddressFamily::Ipv4,
                "192.0.2.16/32",
            ),
            (
                AddressFamily::IPv6,
                nispor::AddressFamily::Ipv6,
                "2001:db8:1::16/128",
            ),
        ] {
            let mut profile = profile_rule();
            profile.family = Some(family);
            profile.priority = Some(100);
            profile.ip_from = Some(source.into());
            let mut kernel = kernel_rule();
            kernel.address_family = np_family;
            kernel.protocol = Some(nispor::RouteProtocol::Static);
            kernel.priority = Some(100);
            kernel.src = Some(source.into());
            let mut owned = vec![profile.clone()];
            assert!(!take_profile_rule(&kernel, false, &mut owned));
            assert_eq!(owned.len(), 1);
            assert!(take_profile_rule(&kernel, true, &mut owned));
            assert!(!take_profile_rule(&kernel, true, &mut owned));
            kernel.table = Some(501);
            assert!(!take_profile_rule(&kernel, true, &mut vec![profile]));
        }
    }

    #[test]
    fn profile_ownership_handles_zero_priority_and_independent_zero_mark_mask()
    {
        let mut profile = profile_rule();
        profile.priority = Some(0);
        let mut kernel = kernel_rule();
        kernel.priority = Some(0);
        kernel.fw_mark = Some(0);
        kernel.fw_mask = Some(0);
        assert!(take_profile_rule(&kernel, true, &mut vec![profile.clone()]));
        profile.fwmask = Some(255);
        kernel.fw_mark = None;
        kernel.fw_mask = Some(255);
        assert!(take_profile_rule(&kernel, true, &mut vec![profile.clone()]));
        kernel.fw_mask = Some(0);
        assert!(!take_profile_rule(&kernel, true, &mut vec![profile]));
    }

    #[test]
    fn profile_ownership_compares_all_selectors_without_wildcards() {
        let mut kernel = kernel_rule();
        let mut profile = profile_rule();
        kernel.iif = Some("eth1".into());
        profile.iif = Some("eth2".into());
        assert!(!take_profile_rule(
            &kernel,
            true,
            &mut vec![profile.clone()]
        ));
        profile.iif = None;
        assert!(!take_profile_rule(
            &kernel,
            true,
            &mut vec![profile.clone()]
        ));
        profile.iif = kernel.iif.clone();
        assert!(take_profile_rule(&kernel, true, &mut vec![profile.clone()]));
        profile.suppress_prefix_length = Some(0);
        assert!(!take_profile_rule(
            &kernel,
            true,
            &mut vec![profile.clone()]
        ));
        kernel.suppress_prefix_len = Some(0);
        assert!(take_profile_rule(&kernel, true, &mut vec![profile.clone()]));
        profile.priority = None;
        assert!(!take_profile_rule(&kernel, true, &mut vec![profile]));
    }

    #[test]
    fn profile_ownership_rejects_unrepresented_headers_flags_and_protocols() {
        let base = kernel_rule();
        let mut variants = Vec::new();
        let mut rule = base.clone();
        rule.tos = 16;
        variants.push(rule);
        let mut rule = base.clone();
        rule.flags.push(nispor::RouteRuleFlag::Other(1 << 31));
        variants.push(rule);
        let mut rule = base.clone();
        rule.tun_id = Some(0);
        variants.push(rule);
        let mut rule = base.clone();
        rule.oif = Some("eth0".into());
        variants.push(rule);
        for protocol in [
            nispor::RouteProtocol::Boot,
            nispor::RouteProtocol::Kernel,
            nispor::RouteProtocol::Dhcp,
        ] {
            let mut rule = base.clone();
            rule.protocol = Some(protocol);
            variants.push(rule);
        }
        let mut rule = base;
        rule.src_port_range = Some(vec![0, 80, 0, 80]);
        variants.push(rule);
        for rule in variants {
            let mut owned = vec![profile_rule()];
            assert!(!take_profile_rule(&rule, true, &mut owned));
            assert_eq!(owned.len(), 1);
        }
    }

    #[test]
    fn profile_ownership_normalizes_default_table_and_all_address_prefix() {
        let mut profile = profile_rule();
        profile.table_id = Some(0);
        profile.ip_from = Some("0.0.0.0/0".into());
        let mut kernel = kernel_rule();
        kernel.table = Some(254);
        assert!(take_profile_rule(&kernel, true, &mut vec![profile.clone()]));
        kernel.table = None;
        assert!(!take_profile_rule(&kernel, true, &mut vec![profile]));
    }

    #[test]
    fn test_mask_only_rule_has_zero_fwmark() {
        let mut np_rule = nispor::RouteRule::default();
        np_rule.action = nispor::RuleAction::Table;
        np_rule.address_family = nispor::AddressFamily::Ipv4;
        np_rule.table = Some(500);
        np_rule.fw_mask = Some(0xff);

        let mut rule =
            get_route_rules(&[np_rule], false).config.unwrap()[0].clone();
        assert_eq!(rule.fwmark, Some(0));
        assert_eq!(rule.fwmask, Some(0xff));
        rule.sanitize().unwrap();
    }
}
