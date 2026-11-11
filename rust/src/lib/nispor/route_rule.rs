// SPDX-License-Identifier: Apache-2.0

use log::warn;

use crate::{
    AddressFamily, ErrorKind, MergedRouteRules, NetworkState, NmstateError,
    RouteRuleAction, RouteRuleEntry, RouteRules,
};

pub(crate) async fn remove_external_route_rules(
    merged_rules: &MergedRouteRules,
    current: &NetworkState,
) -> Result<(), NmstateError> {
    if !merged_rules
        .desired
        .config
        .iter()
        .flatten()
        .any(|r| r.is_absent())
    {
        return Ok(());
    }

    let protected = current
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
    let mut filter = nispor::NetStateFilter::minimum();
    filter.route_rule = Some(Default::default());
    let state = nispor::NetState::retrieve_with_filter_async(&filter)
        .await
        .map_err(rule_removal_error)?;
    let removals =
        plan_route_rule_removals(merged_rules, &state.rules, &protected)?;
    if !removals.is_empty() {
        let mut conf = nispor::NetConf::default();
        conf.rules = Some(removals);
        conf.apply_async().await.map_err(rule_removal_error)?;
    }
    Ok(())
}

fn rule_removal_error(error: nispor::NisporError) -> NmstateError {
    let kind = match error.kind {
        nispor::ErrorKind::PermissionDeny => ErrorKind::PermissionError,
        _ => ErrorKind::PluginFailure,
    };
    NmstateError::new(
        kind,
        format!(
            "External routing rule cleanup failed: {error}. Any completed \
             external deletions will not be rolled back."
        ),
    )
}

pub(crate) fn kernel_rule_is_absent(
    rule: &nispor::RouteRule,
    merged_rules: &MergedRouteRules,
) -> bool {
    get_route_rules_for_apply(std::slice::from_ref(rule))
        .config
        .iter()
        .flatten()
        .any(|current| {
            !current
                .iif
                .as_ref()
                .is_some_and(|name| merged_rules.ignored_ifaces.contains(name))
                && merged_rules
                    .desired
                    .config
                    .iter()
                    .flatten()
                    .any(|rule| rule.is_absent() && rule.is_match(current))
        })
}

pub(crate) fn plan_route_rule_removals(
    merged_rules: &MergedRouteRules,
    rules: &[nispor::RouteRule],
    protected: &[RouteRuleEntry],
) -> Result<Vec<nispor::RouteRuleConf>, NmstateError> {
    let selected: Vec<bool> = rules
        .iter()
        .map(|rule| {
            kernel_rule_is_absent(rule, merged_rules)
                && !get_route_rules_for_apply(std::slice::from_ref(rule))
                    .config
                    .iter()
                    .flatten()
                    .any(|current| {
                        protected.iter().any(|keep| {
                            configured_rule_matches(keep, current, 0)
                        }) || merged_rules
                            .for_apply
                            .iter()
                            .filter(|r| !r.is_absent())
                            .any(|keep| {
                                configured_rule_matches(
                                    keep,
                                    current,
                                    RouteRuleEntry::DEFAULR_ROUTE_TABLE_ID,
                                )
                            })
                    })
        })
        .collect();
    let mut removals = Vec::new();
    // Preserve dump order: an underspecified delete can match a later rule.
    for (rule, selected) in rules.iter().zip(&selected) {
        if *selected {
            removals.push(rule_delete_conf(rule)?);
        }
    }
    for removal in &removals {
        if let Some(protected) =
            rules.iter().zip(&selected).find_map(|(rule, selected)| {
                (!selected && deletion_could_match(removal, rule))
                    .then_some(rule)
            })
        {
            return Err(NmstateError::new(
                ErrorKind::NotSupportedError,
                format!(
                    "Cannot safely delete routing rule at priority {}: its \
                     deletion could also remove a rule that must be kept: \
                     {protected:?}. No external rules were deleted.",
                    removal.priority
                ),
            ));
        }
    }
    Ok(removals)
}

fn configured_rule_matches(
    configured: &RouteRuleEntry,
    current: &RouteRuleEntry,
    default_table: u32,
) -> bool {
    configured.is_ipv6() == current.is_ipv6()
        && configured.priority.unwrap_or(0) == current.priority.unwrap_or(0)
        && configured.action == current.action
        && configured
            .table_id
            .filter(|table| *table != 0)
            .unwrap_or(default_table)
            == current.table_id.unwrap_or(0)
        && normalized_prefix(configured.ip_from.as_deref())
            == normalized_prefix(current.ip_from.as_deref())
        && normalized_prefix(configured.ip_to.as_deref())
            == normalized_prefix(current.ip_to.as_deref())
        && configured.fwmark.unwrap_or(0) == current.fwmark.unwrap_or(0)
        && configured.fwmask.unwrap_or(0) == current.fwmask.unwrap_or(0)
        && configured.iif.as_deref().filter(|iif| !iif.is_empty())
            == current.iif.as_deref().filter(|iif| !iif.is_empty())
        && configured
            .suppress_prefix_length
            .filter(|prefix| *prefix != u32::MAX)
            == current
                .suppress_prefix_length
                .filter(|prefix| *prefix != u32::MAX)
}

fn normalized_prefix(value: Option<&str>) -> Option<(std::net::IpAddr, u8)> {
    value
        .and_then(parse_rule_prefix)
        .filter(|(_, prefix)| *prefix != 0)
}

fn rule_delete_conf(
    rule: &nispor::RouteRule,
) -> Result<nispor::RouteRuleConf, NmstateError> {
    let family = matches!(
        rule.address_family,
        nispor::AddressFamily::Ipv4 | nispor::AddressFamily::Ipv6
    );
    let action = matches!(
        rule.action,
        nispor::RuleAction::Table
            | nispor::RuleAction::Blackhole
            | nispor::RuleAction::Unreachable
            | nispor::RuleAction::Prohibit
    );
    let table = rule.table != Some(0)
        && (rule.action != nispor::RuleAction::Table || rule.table.is_some());
    let networks = [&rule.src, &rule.dst].into_iter().flatten().all(|value| {
        parse_rule_prefix(value).is_some_and(|(ip, _)| {
            ip.is_ipv4() == (rule.address_family == nispor::AddressFamily::Ipv4)
        })
    });
    if !family || !action || !table || !networks {
        return Err(NmstateError::new(
            ErrorKind::NotSupportedError,
            format!(
                "Cannot encode routing rule for deletion: {rule:?}. No \
                 external rules were deleted."
            ),
        ));
    }
    let mut conf = nispor::RouteRuleConf::default();
    conf.remove = true;
    conf.address_family = rule.address_family.clone();
    conf.action = rule.action.clone();
    conf.table = rule.table;
    conf.src.clone_from(&rule.src);
    conf.dst.clone_from(&rule.dst);
    conf.iif.clone_from(&rule.iif);
    conf.priority = rule.priority.unwrap_or(0);
    conf.fw_mark = Some(rule.fw_mark.unwrap_or(0));
    conf.fw_mask = Some(rule.fw_mask.unwrap_or(0));
    conf.suppress_prefix_len = rule.suppress_prefix_len;
    conf.protocol = rule.protocol;
    Ok(conf)
}

// Zero and omitted selectors can be wildcards in a kernel deletion request.
// Overestimating matches rejects ambiguous requests without touching survivors.
fn deletion_could_match(
    request: &nispor::RouteRuleConf,
    rule: &nispor::RouteRule,
) -> bool {
    request.address_family == rule.address_family
        && request.priority == rule.priority.unwrap_or(0)
        && request.action == rule.action
        && request
            .table
            .is_none_or(|table| table == 0 || Some(table) == rule.table)
        && request.protocol.is_none_or(|protocol| {
            matches!(
                protocol,
                nispor::RouteProtocol::Unspec | nispor::RouteProtocol::Other(0)
            ) || Some(protocol) == rule.protocol
        })
        && request
            .fw_mark
            .is_none_or(|mark| mark == 0 || rule.fw_mark == Some(mark))
        && request
            .fw_mask
            .is_none_or(|mask| mask == 0 || rule.fw_mask == Some(mask))
        && request
            .iif
            .as_ref()
            .is_none_or(|iif| iif.is_empty() || rule.iif.as_ref() == Some(iif))
        && request.suppress_prefix_len.is_none_or(|prefix| {
            prefix == u32::MAX || rule.suppress_prefix_len == Some(prefix)
        })
        && prefix_could_match(request.src.as_deref(), rule.src.as_deref())
        && prefix_could_match(request.dst.as_deref(), rule.dst.as_deref())
}

fn prefix_could_match(request: Option<&str>, current: Option<&str>) -> bool {
    let Some((address, prefix)) = request.and_then(parse_rule_prefix) else {
        return true;
    };
    if prefix == 0 {
        return true;
    }
    match current {
        None => false,
        Some(current) => parse_rule_prefix(current)
            .is_none_or(|current| current == (address, prefix)),
    }
}

fn parse_rule_prefix(value: &str) -> Option<(std::net::IpAddr, u8)> {
    let (address, prefix) = match value.split_once('/') {
        Some((address, prefix)) => (
            address.parse::<std::net::IpAddr>().ok()?,
            prefix.parse().ok()?,
        ),
        None => {
            let address = value.parse::<std::net::IpAddr>().ok()?;
            (address, if address.is_ipv4() { 32 } else { 128 })
        }
    };
    (prefix <= if address.is_ipv4() { 32 } else { 128 })
        .then_some((address, prefix))
}

// Unspec includes rules added without an explicit protocol.
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
        rule.apply_ignored =
            np_rule.flags.contains(&nispor::RouteRuleFlag::Invert)
                || np_rule.protocol.is_some_and(|protocol| {
                    !SUPPORTED_STATIC_ROUTE_PROTOCOL.contains(&protocol)
                });
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
