// SPDX-License-Identifier: Apache-2.0

use crate::{
    error::CliError,
    state::{NetworkStateOrPolicy, state_or_policy_from_file},
};

pub(crate) fn validate(matches: &clap::ArgMatches) -> Result<String, CliError> {
    let state_or_policy =
        if let Some(file_path) = matches.value_of("STATE_FILE") {
            state_or_policy_from_file(file_path)?
        } else {
            state_or_policy_from_file("-")?
        };

    let cur_state = match matches.value_of("CURRENT_STATE") {
        Some(file_path) => match state_or_policy_from_file(file_path)? {
            NetworkStateOrPolicy::State(state) => Some(state),
            _ => {
                return Err(CliError::from(
                    "Current state file is not a valid NetworkState",
                ));
            }
        },
        None => None,
    };

    match state_or_policy {
        NetworkStateOrPolicy::Policy(mut policy) => {
            policy.current = cur_state;
            policy.validate()?;
            Ok(serde_yaml::to_string(&policy)?)
        }
        NetworkStateOrPolicy::State(state) => {
            state.validate(cur_state.as_ref())?;
            Ok(serde_yaml::to_string(&state)?)
        }
    }
}
