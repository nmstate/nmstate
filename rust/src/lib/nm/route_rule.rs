// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use super::nm_dbus::{NmIpRouteRule, NmIpRouteRuleAction};
use crate::{
    AddressFamily, ErrorKind, MergedInterfaces, MergedNetworkState,
    NmstateError, RouteEntry, RouteRuleAction, RouteRuleEntry,
};

const DEFAULT_TABLE_ID: u32 = 254; // main route table ID
const LOOPBACK_IFACE_NAME: &str = "lo";

pub(crate) fn nm_rule_to_nmstate(
    is_ipv6: bool,
    nm_rule: &NmIpRouteRule,
) -> Option<RouteRuleEntry> {
    if nm_rule.is_inverted() {
        return None;
    }
    let mut rule = RouteRuleEntry::new();
    if is_ipv6 {
        rule.family = Some(AddressFamily::IPv6);
    } else {
        rule.family = Some(AddressFamily::IPv4);
    }
    if let Some(v) = nm_rule.priority.as_ref() {
        rule.priority = Some(*v as i64);
    }
    if let (Some(from), Some(from_len)) =
        (nm_rule.from.as_ref(), nm_rule.from_len.as_ref())
    {
        rule.ip_from = Some(format!("{from}/{from_len}"));
    }
    if let (Some(to), Some(to_len)) =
        (nm_rule.to.as_ref(), nm_rule.to_len.as_ref())
    {
        rule.ip_to = Some(format!("{to}/{to_len}"));
    }
    if let Some(v) = nm_rule.table.as_ref() {
        rule.table_id = Some(*v);
    }
    if let Some(v) = nm_rule.fw_mark.as_ref() {
        rule.fwmark = Some(*v);
    }
    if let Some(v) = nm_rule.fw_mask.as_ref() {
        rule.fwmask = Some(*v);
    }
    if let Some(v) = nm_rule.iifname.as_ref() {
        rule.iif = Some(v.to_string());
    }
    if let Some(v) = nm_rule.suppress_prefixlength {
        match u32::try_from(v) {
            Ok(i) => rule.suppress_prefix_length = Some(i),
            Err(e) => {
                log::warn!(
                    "BUG: Failed to convert `suppress_prefixlength` got from \
                     NM: {v} to u32: {e}"
                );
            }
        }
    }
    if let Some(v) = nm_rule.action.as_ref() {
        rule.action = Some(match v {
            NmIpRouteRuleAction::Blackhole => RouteRuleAction::Blackhole,
            NmIpRouteRuleAction::Unreachable => RouteRuleAction::Unreachable,
            NmIpRouteRuleAction::Prohibit => RouteRuleAction::Prohibit,
            _ => {
                log::warn!("Unknown NM IP route rule action {v:?}");
                return None;
            }
        });
    }
    Some(rule)
}

// General work flow:
//  * The `current` NetworkState returned by NM plugin has route rules
//    information stored at ip stack level.
//  * For route rule marked as absent, we mark interface holding it as changed.
//  * For normal route rule, we find a interface to hold it and append to
//    `for_apply` state.
pub(crate) fn store_route_rule_config(
    merged_state: &mut MergedNetworkState,
) -> Result<(), NmstateError> {
    let rules = merged_state.rules.for_apply.clone();

    // Explicitly desired rules take precedence over matching absent rules.
    for rule in rules.iter().filter(|rule| rule.is_absent()) {
        apply_absent_rule(&mut merged_state.interfaces, rule);
    }
    for rule in rules.iter().filter(|rule| !rule.is_absent()) {
        append_route_rule(merged_state, rule)?;
    }

    Ok(())
}

fn apply_absent_rule(
    merged_ifaces: &mut MergedInterfaces,
    absent_rule: &RouteRuleEntry,
) {
    for iface in merged_ifaces.kernel_ifaces.values_mut() {
        let cur_iface = if let Some(i) = iface.current.as_ref() {
            i
        } else {
            continue;
        };
        if absent_rule.is_ipv6() {
            if let Some(rules) = cur_iface
                .base_iface()
                .ipv6
                .as_ref()
                .and_then(|i| i.rules.as_ref())
            {
                if rules.iter().all(|rule| !absent_rule.is_match(rule)) {
                    continue;
                }
            } else {
                continue;
            }
        } else if let Some(rules) = cur_iface
            .base_iface()
            .ipv4
            .as_ref()
            .and_then(|i| i.rules.as_ref())
        {
            if rules.iter().all(|rule| !absent_rule.is_match(rule)) {
                continue;
            }
        } else {
            continue;
        }

        if !iface.is_changed() {
            iface.mark_as_changed();
        }
        let cur_iface = if let Some(i) = iface.current.as_ref() {
            i
        } else {
            continue;
        };

        if let Some(apply_iface) = iface.for_apply.as_mut() {
            if apply_iface.base_iface_mut().ipv4.is_none() {
                apply_iface
                    .base_iface_mut()
                    .ipv4
                    .clone_from(&cur_iface.base_iface().ipv4);
            }
            if apply_iface.base_iface_mut().ipv6.is_none() {
                apply_iface
                    .base_iface_mut()
                    .ipv6
                    .clone_from(&cur_iface.base_iface().ipv6);
            }
        }

        let mut remain_rules = HashSet::new();
        if absent_rule.is_ipv6() {
            let full_rules = if let Some(rules) = iface
                .for_apply
                .as_ref()
                .and_then(|i| i.base_iface().ipv6.as_ref())
                .and_then(|i| i.rules.as_ref())
            {
                Some(rules)
            } else {
                cur_iface
                    .base_iface()
                    .ipv6
                    .as_ref()
                    .and_then(|i| i.rules.as_ref())
            };
            if let Some(rules) = full_rules {
                for rule in rules {
                    if !absent_rule.is_match(rule) {
                        remain_rules.insert(rule.clone());
                    }
                }
            }
            if let Some(ip_conf) = iface
                .for_apply
                .as_mut()
                .and_then(|i| i.base_iface_mut().ipv6.as_mut())
            {
                ip_conf.rules = Some(remain_rules);
            };
        } else {
            let full_rules = if let Some(rules) = iface
                .for_apply
                .as_ref()
                .and_then(|i| i.base_iface().ipv4.as_ref())
                .and_then(|i| i.rules.as_ref())
            {
                Some(rules)
            } else {
                cur_iface
                    .base_iface()
                    .ipv4
                    .as_ref()
                    .and_then(|i| i.rules.as_ref())
            };
            if let Some(rules) = full_rules {
                for rule in rules {
                    if !absent_rule.is_match(rule) {
                        remain_rules.insert(rule.clone());
                    }
                }
            }
            if let Some(ip_conf) = iface
                .for_apply
                .as_mut()
                .and_then(|i| i.base_iface_mut().ipv4.as_mut())
            {
                ip_conf.rules = Some(remain_rules);
            };
        }
    }
}

fn append_route_rule(
    merged_state: &mut MergedNetworkState,
    rule: &RouteRuleEntry,
) -> Result<(), NmstateError> {
    let iface_name = find_interface_for_rule(merged_state, rule)?.to_string();

    if let Some(iface) =
        merged_state.interfaces.kernel_ifaces.get_mut(&iface_name)
    {
        // Referring by route-rule `iif` auto-activates a disconnected
        // interface so the rule can be applied without an explicit
        // `interfaces: [{name, state: up}]` entry.
        if !iface.merged.is_up() && !iface.merged.is_ignore() {
            iface.mark_as_up_for_apply();
        } else if !iface.is_changed() {
            iface.mark_as_changed();
        }
        if let Some(apply_iface) = iface.for_apply.as_mut() {
            if rule.is_ipv6() {
                if apply_iface.base_iface().ipv6.is_none() {
                    apply_iface
                        .base_iface_mut()
                        .ipv6
                        .clone_from(&iface.merged.base_iface_mut().ipv6);
                }
                if let Some(ip_conf) =
                    apply_iface.base_iface_mut().ipv6.as_mut()
                {
                    // When desired state has no rules defined, we should
                    // copy current rules first, then append.
                    let rules = ip_conf.rules.get_or_insert_with(|| {
                        iface
                            .merged
                            .base_iface()
                            .ipv6
                            .as_ref()
                            .and_then(|ipv6| ipv6.rules.clone())
                            .unwrap_or_default()
                    });
                    rules.insert(rule.clone());
                }
            } else {
                if apply_iface.base_iface().ipv4.is_none() {
                    apply_iface
                        .base_iface_mut()
                        .ipv4
                        .clone_from(&iface.merged.base_iface_mut().ipv4);
                }
                if let Some(ip_conf) =
                    apply_iface.base_iface_mut().ipv4.as_mut()
                {
                    // When desired state has no rules defined, we should
                    // copy current rules first, then append.
                    let rules = ip_conf.rules.get_or_insert_with(|| {
                        iface
                            .merged
                            .base_iface()
                            .ipv4
                            .as_ref()
                            .and_then(|ipv4| ipv4.rules.clone())
                            .unwrap_or_default()
                    });
                    rules.insert(rule.clone());
                }
            }
        }
    }

    Ok(())
}

// * If rule has `iif`, we use that interface.
// * If rule has table id, we find a interface in desire state configured for
//   that route table
// * fallback to first desired interface with ip stack enabled.
// * fallback to use loop interface.
fn find_interface_for_rule<'a>(
    merged_state: &'a MergedNetworkState,
    rule: &RouteRuleEntry,
) -> Result<&'a str, NmstateError> {
    if let Some(iif) = rule.iif.as_ref() {
        if let Some(iface) = merged_state.interfaces.kernel_ifaces.get(iif) {
            return Ok(iface.merged.name());
        } else {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "The interface {iif} required by route rule {rule} does \
                     not exists"
                ),
            ));
        }
    }

    if let Some(iface_name) =
        find_existing_rule_owner(&merged_state.interfaces, rule)
    {
        return Ok(iface_name);
    }

    let table_id = rule.table_id.unwrap_or(DEFAULT_TABLE_ID);

    // Try interface with desired routes first
    for iface_name in merged_state.routes.route_changed_ifaces.as_slice() {
        if iface_has_route_for_table_id(
            iface_name,
            merged_state,
            rule.is_ipv6(),
            table_id,
        ) {
            return Ok(iface_name);
        }
    }

    let mut des_iface_names: Vec<&str> = merged_state
        .interfaces
        .kernel_ifaces
        .iter()
        .filter_map(|(n, i)| {
            if i.is_changed() {
                Some(n.as_str())
            } else {
                None
            }
        })
        .collect();

    // we should be persistent on choice, hence sort the iface names.
    des_iface_names.sort_unstable();

    // Try interfaces in desire state
    for iface_name in des_iface_names {
        if iface_has_route_for_table_id(
            iface_name,
            merged_state,
            rule.is_ipv6(),
            table_id,
        ) {
            return Ok(iface_name);
        }
    }

    // Fallback to first interface in desire state with IP stack enabled.
    for (iface_name, iface_type) in merged_state.interfaces.insert_order.iter()
    {
        if let Some(iface) = merged_state
            .interfaces
            .get_iface(iface_name, iface_type.clone())
        {
            if rule.is_ipv6() {
                if iface.merged.base_iface().ipv6.as_ref().map(|i| i.enabled)
                    == Some(true)
                {
                    return Ok(iface_name);
                }
            } else if iface.merged.base_iface().ipv4.as_ref().map(|i| i.enabled)
                == Some(true)
            {
                return Ok(iface_name);
            }
        }
    }

    log::info!("Using loopback interface to store route rule {rule}");
    Ok(LOOPBACK_IFACE_NAME)
}

fn find_existing_rule_owner<'a>(
    interfaces: &'a MergedInterfaces,
    rule: &RouteRuleEntry,
) -> Option<&'a str> {
    interfaces
        .kernel_ifaces
        .iter()
        .filter_map(|(name, iface)| {
            let current = iface.current.as_ref()?;
            if !current.is_up() || !iface.merged.is_up() {
                return None;
            }
            let (enabled, current_rules) = if rule.is_ipv6() {
                (
                    iface
                        .merged
                        .base_iface()
                        .ipv6
                        .as_ref()
                        .is_some_and(|ip| ip.enabled),
                    current
                        .base_iface()
                        .ipv6
                        .as_ref()
                        .filter(|ip| ip.enabled)
                        .and_then(|ip| ip.rules.as_ref()),
                )
            } else {
                (
                    iface
                        .merged
                        .base_iface()
                        .ipv4
                        .as_ref()
                        .is_some_and(|ip| ip.enabled),
                    current
                        .base_iface()
                        .ipv4
                        .as_ref()
                        .filter(|ip| ip.enabled)
                        .and_then(|ip| ip.rules.as_ref()),
                )
            };
            if !enabled {
                return None;
            }
            current_rules?
                .iter()
                .any(|current_rule| {
                    rule.is_ipv6() == current_rule.is_ipv6()
                        && rule.is_match(current_rule)
                        && current_rule.is_match(rule)
                })
                .then_some(name.as_str())
        })
        .min()
}

fn iface_has_route_for_table_id(
    iface_name: &str,
    merged_state: &MergedNetworkState,
    is_ipv6: bool,
    table_id: u32,
) -> bool {
    if let Some(routes) = merged_state.routes.merged.get(iface_name) {
        for route in routes.iter().filter(|r| r.is_ipv6() == is_ipv6) {
            if route.table_id == Some(table_id)
                || (route.table_id == Some(RouteEntry::USE_DEFAULT_ROUTE_TABLE)
                    && table_id == DEFAULT_TABLE_ID)
                || (table_id == DEFAULT_TABLE_ID && route.table_id.is_none())
            {
                return true;
            }
        }
    }
    // For interface with `auto_table_id`
    if let Some(iface) = merged_state.interfaces.kernel_ifaces.get(iface_name) {
        if is_ipv6 {
            let iface_table_id = iface
                .merged
                .base_iface()
                .ipv6
                .as_ref()
                .and_then(|i| i.auto_table_id)
                .unwrap_or(DEFAULT_TABLE_ID);
            if iface_table_id == table_id
                || (iface_table_id == RouteEntry::USE_DEFAULT_ROUTE_TABLE
                    && table_id == DEFAULT_TABLE_ID)
            {
                return true;
            }
        } else {
            let iface_table_id = iface
                .merged
                .base_iface()
                .ipv4
                .as_ref()
                .and_then(|i| i.auto_table_id)
                .unwrap_or(DEFAULT_TABLE_ID);
            if iface_table_id == table_id
                || (iface_table_id == RouteEntry::USE_DEFAULT_ROUTE_TABLE
                    && table_id == DEFAULT_TABLE_ID)
            {
                return true;
            }
        }
    }

    false
}
