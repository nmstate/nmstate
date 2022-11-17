// SPDX-License-Identifier: Apache-2.0

use crate::{NetworkState, NmstateError, RouteEntry, Routes};

use super::json::{search_item, update_items};

pub(crate) fn get_route_match(
    prop_path: &[String],
    value: &str,
    state: &NetworkState,
    line: &str,
    pos: usize,
) -> Result<Routes, NmstateError> {
    let mut ret = Routes::new();
    let empty_vec: Vec<RouteEntry> = Vec::new();
    if prop_path.len() != 2 {
        return Err(NmstateError::new_policy_error(
            "No route search pattern found".to_string(),
            line,
            pos,
        ));
    }
    match prop_path[0].as_str() {
        "running" => {
            ret.running = Some(search_item(
                "route",
                &prop_path[1..],
                value,
                state.routes.running.as_ref().unwrap_or(&empty_vec),
                line,
                pos,
            )?);
        }
        "config" => {
            ret.config = Some(search_item(
                "route",
                &prop_path[1..],
                value,
                state.routes.config.as_ref().unwrap_or(&empty_vec),
                line,
                pos,
            )?);
        }
        _ => {
            return Err(NmstateError::new_policy_error(
                "Only support 'running' or 'config' keyword for \
                route searching"
                    .to_string(),
                line,
                pos,
            ));
        }
    };
    Ok(ret)
}

pub(crate) fn update_routes(
    prop_path: &[String],
    value: &str,
    state: &NetworkState,
    line: &str,
    pos: usize,
) -> Result<Routes, NmstateError> {
    let mut ret = Routes::new();
    let empty_vec: Vec<RouteEntry> = Vec::new();
    if prop_path.len() != 2 {
        return Err(NmstateError::new_policy_error(
            "No route replace pattern found".to_string(),
            line,
            pos,
        ));
    }
    match prop_path[0].as_str() {
        "running" => {
            ret.running = Some(update_items(
                "route",
                &prop_path[1..],
                value,
                state.routes.running.as_ref().unwrap_or(&empty_vec),
                line,
                pos,
            )?);
        }
        "config" => {
            ret.config = Some(update_items(
                "route",
                &prop_path[1..],
                value,
                state.routes.config.as_ref().unwrap_or(&empty_vec),
                line,
                pos,
            )?);
        }
        _ => {
            return Err(NmstateError::new_policy_error(
                "Only support 'running' or 'config' keyword for \
                    replacing routes"
                    .to_string(),
                line,
                pos,
            ));
        }
    };
    Ok(ret)
}
