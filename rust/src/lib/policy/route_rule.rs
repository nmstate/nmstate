// SPDX-License-Identifier: Apache-2.0

use crate::{NetworkState, NmstateError, RouteRuleEntry, RouteRules};

use super::json::{search_item, update_items};

pub(crate) fn get_route_rule_match(
    prop_path: &[String],
    value: &str,
    state: &NetworkState,
    line: &str,
    pos: usize,
) -> Result<RouteRules, NmstateError> {
    let mut ret = RouteRules::new();
    let empty_vec: Vec<RouteRuleEntry> = Vec::new();
    if prop_path.len() != 2 {
        return Err(NmstateError::new_policy_error(
            "No route rule search pattern found".to_string(),
            line,
            pos,
        ));
    }
    match prop_path[0].as_str() {
        "config" => {
            ret.config = Some(search_item(
                "route_rule",
                &prop_path[1..],
                value,
                state.rules.config.as_ref().unwrap_or(&empty_vec),
                line,
                pos,
            )?);
        }
        _ => {
            return Err(NmstateError::new_policy_error(
                "Only support 'config' keyword for searching route rules"
                    .to_string(),
                line,
                pos,
            ));
        }
    };
    Ok(ret)
}

pub(crate) fn update_route_rules(
    prop_path: &[String],
    value: Option<&str>,
    state: &NetworkState,
    line: &str,
    pos: usize,
) -> Result<RouteRules, NmstateError> {
    let mut ret = RouteRules::new();
    let empty_vec: Vec<RouteRuleEntry> = Vec::new();
    if prop_path.len() != 2 {
        return Err(NmstateError::new_policy_error(
            "No route rule search pattern found".to_string(),
            line,
            pos,
        ));
    }
    match prop_path[0].as_str() {
        "config" => {
            ret.config = Some(update_items(
                "route_rule",
                &prop_path[1..],
                value,
                state.rules.config.as_ref().unwrap_or(&empty_vec),
                line,
                pos,
            )?);
        }
        _ => {
            return Err(NmstateError::new_policy_error(
                "Only support 'config' keyword for \
                replacing route rules"
                    .to_string(),
                line,
                pos,
            ));
        }
    };
    Ok(ret)
}
