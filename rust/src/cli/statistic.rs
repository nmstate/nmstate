// SPDX-License-Identifier: Apache-2.0

use std::io::Read;

use nmstate::NetworkState;

use crate::error::CliError;

pub(crate) fn statistic(
    matches: &clap::ArgMatches,
) -> Result<String, crate::error::CliError> {
    let desired_state = if let Some(file_path) = matches.value_of("STATE_FILE")
    {
        state_from_file(file_path)?
    } else {
        state_from_file("-")?
    };
    let current_state =
        if let Some(cur_state_file) = matches.value_of("CURRENT_STATE") {
            state_from_file(cur_state_file)?
        } else {
            let mut net_state = NetworkState::new();
            net_state.set_running_config_only(true);
            net_state.retrieve()?;
            net_state
        };

    let statistic = desired_state.statistic(&current_state)?;

    Ok(if matches.is_present("JSON") {
        serde_json::to_string_pretty(&statistic)?
    } else {
        serde_yaml::to_string(&statistic)?
    })
}

fn state_from_file(file_path: &str) -> Result<NetworkState, CliError> {
    let mut content = String::new();
    if file_path == "-" {
        std::io::stdin().read_to_string(&mut content)?;
    } else {
        std::fs::File::open(file_path)?.read_to_string(&mut content)?;
    };
    // Replace non-breaking space '\u{A0}'  to normal space
    let content = content.replace('\u{A0}', " ");

    Ok(NetworkState::new_from_yaml(&content)?)
}
