// SPDX-License-Identifier: Apache-2.0

use log::warn;

use crate::{AddressFamily, RouteRuleAction, RouteRuleEntry, RouteRules};

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
        rule.fwmark = np_rule.fw_mark;
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
    rules.sort();
    ret.config = Some(rules);

    ret
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rule(
        family: nispor::AddressFamily,
        table: u32,
        priority: u32,
    ) -> nispor::RouteRule {
        let mut rule = nispor::RouteRule::default();
        rule.action = nispor::RuleAction::Table;
        rule.address_family = family;
        rule.table = Some(table);
        rule.priority = Some(priority);
        rule.protocol = Some(nispor::RouteProtocol::Static);
        rule
    }

    #[test]
    fn test_retrieved_route_rules_are_sorted() {
        use nispor::AddressFamily::{Ipv4, Ipv6};

        let rules = vec![
            rule(Ipv4, 100, 300),
            rule(Ipv6, 200, 100),
            rule(Ipv4, 100, 100),
            rule(Ipv6, 100, 300),
        ];

        for running_config_only in [false, true] {
            let retrieved = get_route_rules(&rules, running_config_only);
            assert_eq!(
                retrieved
                    .config
                    .unwrap()
                    .iter()
                    .map(|r| (r.family, r.table_id, r.priority))
                    .collect::<Vec<_>>(),
                vec![
                    (Some(AddressFamily::IPv6), Some(100), Some(300)),
                    (Some(AddressFamily::IPv6), Some(200), Some(100)),
                    (Some(AddressFamily::IPv4), Some(100), Some(100)),
                    (Some(AddressFamily::IPv4), Some(100), Some(300)),
                ]
            );
        }
    }

    #[test]
    fn test_retrieved_route_rules_preserve_equal_sort_keys() {
        let mut first = rule(nispor::AddressFamily::Ipv4, 100, 100);
        first.iif = Some("eth2".into());
        let mut second = first.clone();
        second.iif = Some("eth1".into());
        let rules = vec![first.clone(), second, first];

        for running_config_only in [false, true] {
            let retrieved = get_route_rules(&rules, running_config_only);
            assert_eq!(
                retrieved
                    .config
                    .unwrap()
                    .iter()
                    .map(|r| r.iif.as_deref())
                    .collect::<Vec<_>>(),
                vec![Some("eth2"), Some("eth1"), Some("eth2")]
            );
        }
    }

    #[test]
    fn test_retrieved_route_rules_filter_protocols() {
        let mut dynamic = rule(nispor::AddressFamily::Ipv4, 100, 30);
        dynamic.protocol = Some(nispor::RouteProtocol::Dhcp);
        let mut unsupported = rule(nispor::AddressFamily::Ipv4, 100, 5);
        unsupported.protocol = Some(nispor::RouteProtocol::Kernel);
        let mut unspecified = rule(nispor::AddressFamily::Ipv4, 100, 10);
        unspecified.protocol = None;
        let rules = vec![
            dynamic,
            rule(nispor::AddressFamily::Ipv4, 100, 20),
            unsupported,
            unspecified,
        ];

        for (running_config_only, priorities) in [
            (false, vec![Some(10), Some(20), Some(30)]),
            (true, vec![Some(10), Some(20)]),
        ] {
            let retrieved = get_route_rules(&rules, running_config_only);
            assert_eq!(
                retrieved
                    .config
                    .unwrap()
                    .iter()
                    .map(|r| r.priority)
                    .collect::<Vec<_>>(),
                priorities
            );
        }
    }
}
