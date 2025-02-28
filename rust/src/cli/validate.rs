// SPDX-License-Identifier: Apache-2.0

use crate::state::{state_or_policy_from_file, NetworkStateOrPolicy};

pub(crate) fn validate(
    matches: &clap::ArgMatches,
) -> Result<String, crate::error::CliError> {
    let state_or_policy =
        if let Some(file_path) = matches.value_of("STATE_FILE") {
            state_or_policy_from_file(file_path)?
        } else {
            state_or_policy_from_file("-")?
        };
    match state_or_policy {
        NetworkStateOrPolicy::Policy(policy) => {
            Ok(serde_yaml::to_string(&policy)?)
        }
        NetworkStateOrPolicy::State(state) => {
            Ok(serde_yaml::to_string(&state)?)
        }
    }
}
