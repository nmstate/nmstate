// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::io::{Read, Write};

use nmstate::{NetworkPolicy, NetworkState};
use serde::{Deserialize, Serialize};

use crate::error::CliError;

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
#[non_exhaustive]
struct CliNmpolicyCaptureState {
    #[serde(rename = "metaInfo")]
    meta_info: CliNmpolicyCaptureMetaInfo,
    state: NetworkState,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
#[non_exhaustive]
struct CliNmpolicyCaptureMetaInfo {
    time: String,
    version: String,
}

pub(crate) fn policy(matches: &clap::ArgMatches) -> Result<String, CliError> {
    let net_policy = deserilize_from_file::<NetworkPolicy>(
        // clap already confirmed POLICY_FILE is always defined,
        // so unwrap() here is safe.
        matches.value_of("POLICY_FILE").unwrap(),
    )?;
    if net_policy.is_empty() {
        return Ok(String::new());
    }
    let current_state =
        if let Some(current_state_file) = matches.value_of("CURRENT_STATE") {
            deserilize_from_file::<NetworkState>(current_state_file)?
        } else {
            let mut state = NetworkState::new();
            state.retrieve()?;
            state
        };

    let captured_states = if let Some(captured_state_file) =
        matches.value_of("CAPTURED_STATES")
    {
        load_capture_states_from_file(captured_state_file)?
    } else {
        net_policy.capture.execute(&current_state)?
    };

    if let Some(output_capture_file) = matches.value_of("OUTPUT_CAPTURED") {
        store_capture_states_from_file(
            output_capture_file,
            &captured_states,
            matches.is_present("JSON"),
        )?;
    }

    let new_net_state = net_policy
        .desired
        .fill_with_captured_data(&captured_states)?;

    if new_net_state.is_empty() {
        return Ok("".to_string());
    }

    Ok(if matches.is_present("JSON") {
        serde_json::to_string_pretty(&new_net_state)?
    } else {
        serde_yaml::to_string(&new_net_state)?
    })
}

fn deserilize_from_file<T>(file_path: &str) -> Result<T, CliError>
where
    T: for<'de> serde::Deserialize<'de> + Default,
{
    let mut fd = std::fs::File::open(file_path)?;
    let mut content = String::new();
    fd.read_to_string(&mut content)?;
    if content.is_empty() {
        return Ok(T::default());
    }
    match serde_yaml::from_str(&content) {
        Ok(n) => Ok(n),
        Err(yaml_error) => match serde_json::from_str(&content) {
            Ok(n) => Ok(n),
            Err(json_error) => Err(format!(
                "Failed to load from file, \
                     tried both YAML and JSON format. Errors: {yaml_error}, {json_error}"
            )
            .into()),
        },
    }
}

fn load_capture_states_from_file(
    captured_state_file: &str,
) -> Result<HashMap<String, NetworkState>, CliError> {
    let mut states = HashMap::new();
    let mut cli_cap_states = deserilize_from_file::<
        HashMap<String, CliNmpolicyCaptureState>,
    >(captured_state_file)?;
    for (name, cli_cap_state) in cli_cap_states.drain() {
        states.insert(name, cli_cap_state.state);
    }

    Ok(states)
}

fn store_capture_states_from_file(
    file_path: &str,
    states: &HashMap<String, NetworkState>,
    use_json_format: bool,
) -> Result<(), CliError> {
    let mut cli_cap_states = HashMap::new();
    for (name, state) in states.iter() {
        cli_cap_states.insert(
            name.to_string(),
            CliNmpolicyCaptureState {
                meta_info: CliNmpolicyCaptureMetaInfo {
                    time: get_utc_time_in_rfc3339_format(),
                    version: "0".to_string(),
                },
                state: state.clone(),
            },
        );
    }
    let states_string = if use_json_format {
        serde_json::to_string_pretty(&cli_cap_states)?
    } else {
        serde_yaml::to_string(&cli_cap_states)?
    };
    let mut fd = std::fs::OpenOptions::new()
        .write(true)
        .truncate(true)
        .create(true)
        .open(file_path)
        .map_err(|e| {
            CliError::from(format!(
                "Failed to store captured states to file {file_path}: {e}"
            ))
        })?;
    fd.write_all(states_string.as_bytes())?;
    Ok(())
}

fn get_utc_time_in_rfc3339_format() -> String {
    chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true)
}
