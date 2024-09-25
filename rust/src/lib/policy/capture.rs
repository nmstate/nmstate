// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde::{
    ser::SerializeMap, Deserialize, Deserializer, Serialize, Serializer,
};

use crate::{ErrorKind, NetworkState, NmstateError};

use super::{
    iface::{get_iface_match, update_ifaces},
    json::{get_value_from_json, value_retain_only, value_to_string},
    route::{get_route_match, update_routes},
    route_rule::{get_route_rule_match, update_route_rules},
    token::{parse_str_to_capture_tokens, NetworkCaptureToken},
};

pub(crate) const PROPERTY_SPLITTER: &str = ".";

#[derive(Clone, Debug, Default, PartialEq, Eq)]
#[non_exhaustive]
pub struct NetworkCaptureRules {
    pub cmds: Vec<(String, NetworkCaptureCommand)>,
}

impl<'de> Deserialize<'de> for NetworkCaptureRules {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let map = serde_json::Map::<String, serde_json::Value>::deserialize(
            deserializer,
        )?;
        let mut cmds: Vec<(String, NetworkCaptureCommand)> = Vec::new();

        for (k, v) in map.iter() {
            if let serde_json::Value::String(s) = v {
                cmds.push((
                    k.to_string(),
                    NetworkCaptureCommand::parse(s.as_str())
                        .map_err(serde::de::Error::custom)?,
                ));
            } else {
                return Err(serde::de::Error::custom(format!(
                    "Expecting a string, but got {v}"
                )));
            }
        }
        log::debug!("Parsed into commands {:?}", cmds);
        Ok(NetworkCaptureRules { cmds })
    }
}

impl Serialize for NetworkCaptureRules {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut map = serializer.serialize_map(Some(self.cmds.len()))?;
        for (name, value) in &self.cmds {
            map.serialize_entry(&name, &value)?;
        }
        map.end()
    }
}

impl NetworkCaptureRules {
    pub fn execute(
        &self,
        current: &NetworkState,
    ) -> Result<HashMap<String, NetworkState>, NmstateError> {
        let mut ret = HashMap::new();
        for (var_name, cmd) in self.cmds.as_slice() {
            let matched_state = cmd.execute(current, &ret)?;
            log::debug!(
                "Found match state for {}: {:?}",
                var_name,
                matched_state
            );
            ret.insert(var_name.to_string(), matched_state);
        }
        Ok(ret)
    }

    pub(crate) fn is_empty(&self) -> bool {
        self.cmds.is_empty()
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct NetworkCaptureCommand {
    pub(crate) key: NetworkCaptureToken,
    pub(crate) key_capture: Option<String>,
    pub(crate) key_capture_pos: usize,
    pub(crate) action: NetworkCaptureAction,
    pub(crate) value: NetworkCaptureToken,
    pub(crate) value_capture: Option<String>,
    pub(crate) value_capture_pos: usize,
    pub(crate) line: String,
}

impl NetworkCaptureCommand {
    pub(crate) fn parse(line: &str) -> Result<Self, NmstateError> {
        let line = line
            .trim()
            .replace(
                '\u{A0}', // Non-breaking space
                " ",
            )
            .trim()
            .to_string();

        let mut ret = Self {
            line,
            ..Default::default()
        };
        let tokens = parse_str_to_capture_tokens(ret.line.as_str())?;
        let tokens = tokens.as_slice();

        if let Some(pos) = tokens
            .iter()
            .position(|c| matches!(c, NetworkCaptureToken::Pipe(_)))
        {
            ret.key_capture = Some(get_input_capture_source(
                &tokens[..pos],
                ret.line.as_str(),
                &tokens[pos],
            )?);
            if pos + 1 < tokens.len() {
                process_tokens_without_pipe(&mut ret, &tokens[pos + 1..])?;
            }
        } else {
            process_tokens_without_pipe(&mut ret, tokens)?;
        }

        Ok(ret)
    }
}

impl Serialize for NetworkCaptureCommand {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(self.line.as_str())
    }
}

impl NetworkCaptureCommand {
    pub(crate) fn execute(
        &self,
        current: &NetworkState,
        captures: &HashMap<String, NetworkState>,
    ) -> Result<NetworkState, NmstateError> {
        let input = if let Some(cap_name) = self.key_capture.as_ref() {
            if let Some(cap) = captures.get(cap_name) {
                cap.clone()
            } else {
                return Err(NmstateError::new_policy_error(
                    format!("Capture {cap_name} not found"),
                    self.line.as_str(),
                    self.key_capture_pos,
                ));
            }
        } else {
            current.clone()
        };
        if self.action == NetworkCaptureAction::None {
            if let NetworkCaptureToken::Path(keys, _) = &self.key {
                if keys.is_empty() {
                    return Ok(NetworkState::new());
                }
                let mut input_value =
                    serde_json::to_value(&input).map_err(|e| {
                        NmstateError::new(
                            ErrorKind::Bug,
                            format!(
                                "Failed to convert NetworkState {input:?} \
                                 to serde_json value: {e}"
                            ),
                        )
                    })?;
                value_retain_only(&mut input_value, keys.as_slice());
                return NetworkState::deserialize(&input_value).map_err(|e| {
                    NmstateError::new(
                        ErrorKind::Bug,
                        format!(
                            "Failed to convert NetworkState {input_value:?} \
                             from serde_json value: {e:?}"
                        ),
                    )
                });
            } else {
                return Ok(NetworkState::new());
            }
        }

        let value_input = if let Some(cap_name) = self.value_capture.as_ref() {
            if let Some(cap) = captures.get(cap_name) {
                cap.clone()
            } else {
                return Err(NmstateError::new_policy_error(
                    format!("Capture {cap_name} not found"),
                    self.line.as_str(),
                    self.key_capture_pos,
                ));
            }
        } else {
            current.clone()
        };
        let matching_value =
            match get_value(&self.value, &value_input, self.line.as_str())? {
                serde_json::Value::Null => None,
                v => Some(value_to_string(&v)),
            };
        let matching_value_str = matching_value.clone().unwrap_or_default();

        let mut ret = NetworkState::new();

        let (keys, key_pos) =
            if let NetworkCaptureToken::Path(keys, pos) = &self.key {
                (keys.as_slice(), pos)
            } else {
                return Err(NmstateError::new(
                    ErrorKind::Bug,
                    format!(
                        "The NetworkCaptureCommand.key is not Path but {:?}",
                        &self.key
                    ),
                ));
            };

        match keys.first().map(String::as_str) {
            Some("routes") => {
                ret.routes = match self.action {
                    NetworkCaptureAction::Equal => get_route_match(
                        &keys[1..],
                        matching_value_str.as_str(),
                        &input,
                        self.line.as_str(),
                        key_pos + "routes.".len(),
                    )?,
                    NetworkCaptureAction::Replace => update_routes(
                        &keys[1..],
                        matching_value.as_deref(),
                        &input,
                        self.line.as_str(),
                        key_pos + "routes.".len(),
                    )?,
                    NetworkCaptureAction::None => unreachable!(),
                }
            }
            Some("route-rules") => {
                ret.rules = match self.action {
                    NetworkCaptureAction::Equal => get_route_rule_match(
                        &keys[1..],
                        matching_value_str.as_str(),
                        &input,
                        self.line.as_str(),
                        key_pos + "route-rules.".len(),
                    )?,
                    NetworkCaptureAction::Replace => update_route_rules(
                        &keys[1..],
                        matching_value.as_deref(),
                        &input,
                        self.line.as_str(),
                        key_pos + "route-rules.".len(),
                    )?,
                    NetworkCaptureAction::None => unreachable!(),
                }
            }
            Some("interfaces") => {
                ret.interfaces = match self.action {
                    NetworkCaptureAction::Equal => get_iface_match(
                        &keys[1..],
                        matching_value_str.as_str(),
                        &input,
                        self.line.as_str(),
                        key_pos + "interfaces.".len(),
                    )?,
                    NetworkCaptureAction::Replace => update_ifaces(
                        &keys[1..],
                        matching_value.as_deref(),
                        &input,
                        self.line.as_str(),
                        key_pos + "interfaces.".len(),
                    )?,
                    NetworkCaptureAction::None => unreachable!(),
                }
            }
            Some(v) => {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!("Unsupported capture keyword '{v}'"),
                ));
            }
            None => {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Invalid empty keyword".to_string(),
                ));
            }
        }
        Ok(ret)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum NetworkCaptureAction {
    None,
    Equal,
    Replace,
}

impl Default for NetworkCaptureAction {
    fn default() -> Self {
        Self::None
    }
}

impl std::fmt::Display for NetworkCaptureAction {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Equal => "==",
                Self::Replace => ":=",
                Self::None => "",
            }
        )
    }
}

pub(crate) fn get_value(
    prop_path: &NetworkCaptureToken,
    state: &NetworkState,
    line: &str,
) -> Result<serde_json::Value, NmstateError> {
    match prop_path {
        NetworkCaptureToken::Path(prop_path, pos) => {
            match serde_json::to_value(state)
                .map_err(|e| {
                    NmstateError::new(
                        ErrorKind::Bug,
                        format!(
                            "Failed to convert NetworkState {state:?} \
                            to serde_json value: {e}"
                        ),
                    )
                })?
                .as_object()
            {
                Some(state_value) => {
                    get_value_from_json(prop_path, state_value, line, *pos)
                }
                None => Err(NmstateError::new(
                    ErrorKind::Bug,
                    format!(
                        "Failed to convert NetworkState {state:?} to serde_json map",
                    ),
                )),
            }
        }

        NetworkCaptureToken::Value(v, _) => {
            Ok(serde_json::Value::String(v.clone()))
        }
        NetworkCaptureToken::Null(_) => {
            Ok(serde_json::Value::Null)
        }
        _ => todo!(),
    }
}

fn get_input_capture_source(
    tokens: &[NetworkCaptureToken],
    line: &str,
    pipe_token: &NetworkCaptureToken,
) -> Result<String, NmstateError> {
    match tokens.first() {
        Some(NetworkCaptureToken::Path(path, pos)) => {
            if path.len() != 2 || path[0] != "capture" {
                Err(NmstateError::new_policy_error(
                    "The pipe action should always in format of \
                    'capture.<capture_name>'"
                        .to_string(),
                    line,
                    *pos,
                ))
            } else {
                Ok(path[1].to_string())
            }
        }
        Some(NetworkCaptureToken::Value(_, pos)) => {
            Err(NmstateError::new_policy_error(
                "The pipe action should always in format of \
                'capture.<capture_name>'"
                    .to_string(),
                line,
                *pos,
            ))
        }
        Some(token) => Err(NmstateError::new_policy_error(
            "The pipe action should always in format of \
                'capture.<capture_name>'"
                .to_string(),
            line,
            token.pos(),
        )),
        None => Err(NmstateError::new_policy_error(
            "The pipe action should always in format of \
                'capture.<capture_name>'"
                .to_string(),
            line,
            pipe_token.pos(),
        )),
    }
}

fn get_condition_key(
    tokens: &[NetworkCaptureToken],
    line: &str,
    action_token: &NetworkCaptureToken,
) -> Result<(NetworkCaptureToken, Option<(String, usize)>), NmstateError> {
    if tokens.len() == 1 {
        if let Some(NetworkCaptureToken::Path(path, pos)) = tokens.first() {
            if path.first() == Some(&"capture".to_string()) {
                if path.len() <= 2 {
                    return Err(NmstateError::new_policy_error(
                        "No property path after capture name".to_string(),
                        line,
                        *pos,
                    ));
                }
                Ok((
                    NetworkCaptureToken::Path(
                        path[2..].to_vec(),
                        pos + "capture.".len() + path[1].len(),
                    ),
                    Some((path[1].to_string(), pos + "capture.".len())),
                ))
            } else {
                Ok((tokens[0].clone(), None))
            }
        } else {
            Err(NmstateError::new_policy_error(
                "The equal or replace action should always start with \
                property path"
                    .to_string(),
                line,
                tokens[0].pos(),
            ))
        }
    } else {
        Err(NmstateError::new_policy_error(
            "The equal or replace action should always start with \
            property path"
                .to_string(),
            line,
            action_token.pos(),
        ))
    }
}

fn get_condition_value(
    tokens: &[NetworkCaptureToken],
    line: &str,
    action_token: &NetworkCaptureToken,
) -> Result<(NetworkCaptureToken, Option<(String, usize)>), NmstateError> {
    if tokens.len() != 1 {
        return Err(NmstateError::new_policy_error(
            "The equal or replace action should end with single value or \
            property path"
                .to_string(),
            line,
            if tokens.len() >= 2 {
                tokens[0].pos()
            } else {
                action_token.pos()
            },
        ));
    }

    match tokens[0] {
        NetworkCaptureToken::Path(ref path, pos) => {
            Ok(if path.first() == Some(&"capture".to_string()) {
                if path.len() < 3 {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "When using equal action to match against \
                            captured data, the correct format should be \
                            'interfaces.name == \
                            capture.default-gw.interfaces.0.name', \
                            but got: {line}"
                        ),
                    ));
                }
                (
                    NetworkCaptureToken::Path(
                        path[2..].to_vec(),
                        pos + format!("capture.{}.", path[1]).chars().count(),
                    ),
                    Some((path[1].to_string(), pos + "capture.".len())),
                )
            } else {
                (tokens[0].clone(), None)
            })
        }
        NetworkCaptureToken::Value(_, _) => Ok((tokens[0].clone(), None)),
        NetworkCaptureToken::Null(_) => Ok((tokens[0].clone(), None)),
        _ => Err(NmstateError::new(
            ErrorKind::InvalidArgument,
            format!(
                "The equal action should end with single value or \
                property path but got: {line}"
            ),
        )),
    }
}

fn process_tokens_without_pipe(
    ret: &mut NetworkCaptureCommand,
    tokens: &[NetworkCaptureToken],
) -> Result<(), NmstateError> {
    let line = ret.line.as_str();
    if let Some(pos) = tokens
        .iter()
        .position(|c| matches!(c, &NetworkCaptureToken::Equal(_)))
    {
        if pos + 1 >= tokens.len() {
            return Err(NmstateError::new_policy_error(
                "The equal action got no value defined afterwards".to_string(),
                line,
                tokens[pos].pos(),
            ));
        }
        ret.action = NetworkCaptureAction::Equal;
        let (key, key_capture) =
            get_condition_key(&tokens[..pos], line, &tokens[pos])?;
        if ret.key_capture.is_none() {
            if let Some((cap_name, pos)) = key_capture {
                ret.key_capture = Some(cap_name);
                ret.key_capture_pos = pos;
            }
        }
        ret.key = key;
        let (value, value_capture) =
            get_condition_value(&tokens[pos + 1..], line, &tokens[pos])?;
        ret.value = value;
        if let Some((cap_name, pos)) = value_capture {
            ret.value_capture = Some(cap_name);
            ret.value_capture_pos = pos;
        }
    } else if let Some(pos) = tokens
        .iter()
        .position(|c| matches!(c, &NetworkCaptureToken::Replace(_)))
    {
        if pos + 1 > tokens.len() {
            return Err(NmstateError::new_policy_error(
                "The replace action got no value defined afterwards"
                    .to_string(),
                line,
                tokens[pos].pos(),
            ));
        }
        ret.action = NetworkCaptureAction::Replace;
        let (key, key_capture) =
            get_condition_key(&tokens[..pos], line, &tokens[pos])?;
        if ret.key_capture.is_none() {
            if let Some((cap_name, pos)) = key_capture {
                ret.key_capture = Some(cap_name);
                ret.key_capture_pos = pos;
            }
        }
        ret.key = key;
        let (value, value_capture) =
            get_condition_value(&tokens[pos + 1..], line, &tokens[pos])?;
        ret.value = value;
        if let Some((cap_name, pos)) = value_capture {
            ret.value_capture = Some(cap_name);
            ret.value_capture_pos = pos;
        }
    } else if let Some(NetworkCaptureToken::Path(_, _)) = tokens.first() {
        // User just want to remove all information except the defined one
        ret.action = NetworkCaptureAction::None;
        ret.key = tokens[0].clone()
    }
    Ok(())
}
