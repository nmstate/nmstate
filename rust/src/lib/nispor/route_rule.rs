// SPDX-License-Identifier: Apache-2.0

use log::warn;

use crate::{AddressFamily, RouteRuleAction, RouteRuleEntry, RouteRules};

// Due to a bug in NetworkManager all route rules added using NetworkManager are
// using RTM_PROTOCOL UnSpec. Therefore, we need to support it until it is
// fixed.
const SUPPORTED_STATIC_ROUTE_PROTOCOL: [nispor::RouteProtocol; 4] = [
    nispor::RouteProtocol::Boot,
    nispor::RouteProtocol::Static,
    nispor::RouteProtocol::Kernel,
    nispor::RouteProtocol::UnSpec,
];

const SUPPORTED_ROUTE_PROTOCOL: [nispor::RouteProtocol; 9] = [
    nispor::RouteProtocol::Boot,
    nispor::RouteProtocol::Static,
    nispor::RouteProtocol::Ra,
    nispor::RouteProtocol::Dhcp,
    nispor::RouteProtocol::Mrouted,
    nispor::RouteProtocol::KeepAlived,
    nispor::RouteProtocol::Babel,
    nispor::RouteProtocol::Kernel,
    nispor::RouteProtocol::UnSpec,
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
                log::debug!("Got unsupported route rule {:?}", np_rule);
                continue;
            }
        }
        // Filter out the routes with protocols that we do not support
        if let Some(rule_protocol) = np_rule.protocol.as_ref() {
            if !protocols.contains(rule_protocol) {
                continue;
            }
            // We only support modifying local rule from kernel, the others
            // should be ignored.
            if *rule_protocol == nispor::RouteProtocol::Kernel
                && np_rule.table != Some(255)
            {
                continue;
            }
        }
        rule.iif = np_rule.iif.clone();
        rule.ip_to = np_rule.dst.clone();
        rule.ip_from = np_rule.src.clone();
        rule.table_id = np_rule.table;
        rule.priority = np_rule.priority.map(i64::from);
        rule.fwmark = np_rule.fw_mark;
        rule.fwmask = np_rule.fw_mask;
        rule.family = match np_rule.address_family {
            nispor::AddressFamily::IPv4 => Some(AddressFamily::IPv4),
            nispor::AddressFamily::IPv6 => Some(AddressFamily::IPv6),
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
