// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::fmt::Write;

use serde::{Deserialize, Serialize};

use crate::{ErrorKind, NetworkState, NmstateError};

use super::{
    capture::get_value,
    token::{
        parse_str_to_template_tokens, NetworkCaptureToken, NetworkTemplateToken,
    },
};

#[derive(Clone, Debug, Deserialize, Serialize, Default, PartialEq, Eq)]
#[non_exhaustive]
pub struct NetworkStateTemplate(HashMap<String, serde_json::Value>);

impl NetworkStateTemplate {
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }

    pub fn fill_with_captured_data(
        &self,
        capture_results: &HashMap<String, NetworkState>,
    ) -> Result<NetworkState, NmstateError> {
        log::debug!("fill_with_captured_data {:?} {:?}", self, capture_results);

        let mut desire_state_value = self.0.clone();
        let mut new_values = HashMap::new();
        for (k, v) in desire_state_value.iter_mut() {
            if let Some(new_value) = resolve_capture_data(v, capture_results)? {
                new_values.insert(k.to_string(), new_value);
            }
        }
        for (k, v) in new_values.drain() {
            desire_state_value.insert(k, v);
        }

        serde_json::from_value(serde_json::Value::from_iter(
            desire_state_value.drain(),
        ))
        .map_err(|e| {
            NmstateError::new(ErrorKind::InvalidArgument, format!("{e}"))
        })
    }
}

fn resolve_capture_data(
    value: &mut serde_json::Value,
    capture_results: &HashMap<String, NetworkState>,
) -> Result<Option<serde_json::Value>, NmstateError> {
    if let serde_json::Value::String(value) = value {
        let line = value.as_str().trim();
        let tokens = parse_str_to_template_tokens(line)?;

        if let (Some(token_start_pos), Some(token_end_pos)) = (
            tokens.as_slice().iter().position(|t| {
                matches!(t, &NetworkTemplateToken::ReferenceStart(_))
            }),
            tokens.as_slice().iter().position(|t| {
                matches!(t, &NetworkTemplateToken::ReferenceEnd(_))
            }),
        ) {
            let cap_prop_token = &tokens[token_start_pos + 1];
            if let NetworkTemplateToken::Path(cap_props, pos) = cap_prop_token {
                let resolved = get_capture_value(
                    cap_props.as_slice(),
                    capture_results,
                    line,
                    cap_prop_token.pos(),
                )?;
                if (!resolved.is_string())
                    && (token_start_pos != 0
                        || token_end_pos != tokens.len() - 1)
                {
                    return Err(NmstateError::new_policy_error(
                        "The resolved reference result is object or array, \
                        hence you cannot add prefix or postfix"
                            .to_string(),
                        line,
                        *pos,
                    ));
                }
                if let serde_json::Value::String(resolved) = resolved {
                    let mut new_value = String::new();
                    // Append resolved to original string
                    if token_start_pos != 0 {
                        for token in &tokens[..token_start_pos] {
                            if let NetworkTemplateToken::Value(s, _) = token {
                                write!(new_value, "{}", s.as_str()).ok();
                            } else {
                                return Err(NmstateError::new_policy_error(
                                    "Only allows string before reference"
                                        .to_string(),
                                    line,
                                    token.pos(),
                                ));
                            }
                        }
                    }
                    write!(new_value, "{resolved}").ok();
                    if token_end_pos < tokens.len() - 1 {
                        for token in &tokens[token_end_pos + 1..] {
                            if let NetworkTemplateToken::Value(s, _) = token {
                                write!(new_value, "{}", s.as_str()).ok();
                            } else {
                                return Err(NmstateError::new_policy_error(
                                    "Only allows string after reference"
                                        .to_string(),
                                    line,
                                    token.pos(),
                                ));
                            }
                        }
                    }
                    return Ok(Some(serde_json::Value::String(new_value)));
                } else {
                    return Ok(Some(resolved));
                }
            } else {
                return Err(NmstateError::new_policy_error(
                    "Only allow property path between reference \
                        start {{ and reference end }}"
                        .to_string(),
                    line,
                    tokens[token_start_pos].pos(),
                ));
            }
        } else {
            return Ok(None);
        }
    } else if let Some(value) = value.as_object_mut() {
        let mut pending_changes: HashMap<String, serde_json::Value> =
            HashMap::new();
        for (k, v) in value.iter_mut() {
            if let Some(new_value) = resolve_capture_data(v, capture_results)? {
                log::debug!("Changing {} to {} for {}", v, new_value, k);
                pending_changes.insert(k.to_string(), new_value);
            }
        }
        for (k, v) in pending_changes.drain() {
            value.insert(k, v);
        }
    } else if let Some(items) = value.as_array_mut() {
        let mut pending_changes: Vec<(usize, serde_json::Value)> = Vec::new();
        for (index, item) in items.iter_mut().enumerate() {
            if let Some(new_item) = resolve_capture_data(item, capture_results)?
            {
                log::debug!("Changing {} to {}", item, new_item);
                pending_changes.push((index, new_item));
            }
        }
        for (index, item) in pending_changes {
            items[index] = item;
        }
    }
    Ok(None)
}

fn get_capture_value(
    prop_path: &[String],
    captures: &HashMap<String, NetworkState>,
    line: &str,
    pos: usize,
) -> Result<serde_json::Value, NmstateError> {
    if prop_path.len() < 2 {
        return Err(NmstateError::new_policy_error(
            "Invalid capture reference string, should be in the format \
            capture.<capture_name>.<property_path>"
                .to_string(),
            line,
            pos,
        ));
    }
    if &prop_path[0] != "capture" {
        return Err(NmstateError::new_policy_error(
            "Can only refer to captured data".to_string(),
            line,
            pos,
        ));
    }
    let capture = match captures.get(&prop_path[1].to_string()) {
        Some(c) => {
            log::debug!("Found capture {} {:?}", &prop_path[1], c);
            c
        }
        None => {
            return Err(NmstateError::new_policy_error(
                format!("Failed to find capture {}", &prop_path[1],),
                line,
                pos + "capture.".len(),
            ));
        }
    };
    get_value(
        &NetworkCaptureToken::Path(
            prop_path[2..].to_vec(),
            pos + format!("capture.{}.", &prop_path[1]).chars().count(),
        ),
        capture,
        line,
    )
}
