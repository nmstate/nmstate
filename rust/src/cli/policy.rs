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
                "Failed to load from file, tried both YAML and JSON format. \
                 Errors: {yaml_error}, {json_error}"
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
    time::OffsetDateTime::now_utc()
        .format(&time::format_description::well_known::Rfc3339)
        .expect("Failed to format time as RFC3339")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_utc_time_in_rfc3339_format() {
        let timestamp = get_utc_time_in_rfc3339_format();

        // RFC3339 format: YYYY-MM-DDTHH:MM:SSZ or YYYY-MM-DDTHH:MM:SS.fffffZ
        // Example: "2025-11-26T14:30:45Z" or "2025-11-26T14:30:45.123456Z"

        // Verify minimum length (at least "YYYY-MM-DDTHH:MM:SSZ" = 20 chars)
        assert!(timestamp.len() >= 20, "Timestamp too short: {}", timestamp);

        // Verify it ends with 'Z' (UTC timezone)
        assert!(
            timestamp.ends_with('Z'),
            "Timestamp should end with 'Z' for UTC: {}",
            timestamp
        );

        // Verify it contains 'T' separator between date and time
        assert!(
            timestamp.contains('T'),
            "Timestamp should contain 'T' separator: {}",
            timestamp
        );

        // Verify date part format (YYYY-MM-DD)
        let parts: Vec<&str> = timestamp.split('T').collect();
        assert_eq!(parts.len(), 2, "Should have date and time parts");

        let date_part = parts[0];
        assert_eq!(
            date_part.len(),
            10,
            "Date part should be 10 chars (YYYY-MM-DD): {}",
            date_part
        );
        assert_eq!(
            &date_part[4..5],
            "-",
            "Date should have dash at position 4"
        );
        assert_eq!(
            &date_part[7..8],
            "-",
            "Date should have dash at position 7"
        );

        // Verify time part starts with HH:MM:SS
        let time_part = parts[1].trim_end_matches('Z');
        assert!(
            time_part.len() >= 8,
            "Time part should be at least HH:MM:SS (8 chars): {}",
            time_part
        );

        // Verify year is reasonable (between 2020 and 2100)
        let year: u32 = date_part[0..4]
            .parse()
            .expect("Year should be a valid number");
        assert!(
            (2020..=2100).contains(&year),
            "Year should be reasonable: {}",
            year
        );

        // Verify month is valid (01-12)
        let month: u32 = date_part[5..7]
            .parse()
            .expect("Month should be a valid number");
        assert!(
            (1..=12).contains(&month),
            "Month should be between 1 and 12: {}",
            month
        );

        // Verify day is valid (01-31)
        let day: u32 = date_part[8..10]
            .parse()
            .expect("Day should be a valid number");
        assert!(
            (1..=31).contains(&day),
            "Day should be between 1 and 31: {}",
            day
        );

        // Verify hour is valid (00-23)
        let hour: u32 = time_part[0..2]
            .parse()
            .expect("Hour should be a valid number");
        assert!(hour <= 23, "Hour should be between 0 and 23: {}", hour);

        // Verify minute is valid (00-59)
        let minute: u32 = time_part[3..5]
            .parse()
            .expect("Minute should be a valid number");
        assert!(
            minute <= 59,
            "Minute should be between 0 and 59: {}",
            minute
        );

        // Verify second is valid (00-59) or is leap second (60)
        let second: u32 = time_part[6..8]
            .parse()
            .expect("Second should be a valid number");
        assert!(
            second <= 60,
            "Second should be between 0 and 60: {}",
            second
        );
    }

    #[test]
    fn test_rfc3339_format_consistency() {
        // Call the function multiple times and verify all produce valid RFC3339
        for _ in 0..5 {
            let timestamp = get_utc_time_in_rfc3339_format();
            assert!(timestamp.len() >= 20);
            assert!(timestamp.ends_with('Z'));
            assert!(timestamp.contains('T'));

            // Small delay to ensure timestamps are different
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
    }

    #[test]
    fn test_rfc3339_parseable() {
        // Verify the timestamp can be parsed back using the time crate
        let timestamp = get_utc_time_in_rfc3339_format();

        let parsed = time::OffsetDateTime::parse(
            &timestamp,
            &time::format_description::well_known::Rfc3339,
        );

        assert!(
            parsed.is_ok(),
            "Generated timestamp should be parseable: {}",
            timestamp
        );

        let parsed_dt = parsed.unwrap();
        assert_eq!(
            parsed_dt.offset(),
            time::UtcOffset::UTC,
            "Parsed timestamp should be UTC"
        );
    }
}
