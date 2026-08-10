// SPDX-License-Identifier: Apache-2.0

use nmstate::NetworkState;

use crate::{error::CliError, state::state_from_file};

pub(crate) fn gen_revert(
    matches: &clap::ArgMatches,
) -> Result<String, CliError> {
    let desired_state =
        if let Some(file_path) = matches.get_one::<String>("STATE_FILE") {
            state_from_file(file_path)?
        } else {
            state_from_file("-")?
        };
    let current_state = if let Some(cur_state_file) =
        matches.get_one::<String>("CURRENT_STATE")
    {
        state_from_file(cur_state_file)?
    } else {
        let mut net_state = NetworkState::new();
        net_state.set_running_config_only(true);
        net_state.retrieve()?;
        net_state
    };

    let new_state = desired_state.generate_revert(&current_state)?;

    Ok(if matches.get_flag("JSON") {
        serde_json::to_string_pretty(&new_state)?
    } else {
        rmsd_yaml::to_string(&new_state)?
    })
}
