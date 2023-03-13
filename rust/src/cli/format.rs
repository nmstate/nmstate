// SPDX-License-Identifier: Apache-2.0

use nmstate::NetworkState;
use std::io::Read;

use crate::error::CliError;

pub(crate) fn format(state_file: &str) -> Result<String, CliError> {
    let mut content = String::new();
    if state_file == "-" {
        std::io::stdin().read_to_string(&mut content)?;
    } else {
        std::fs::File::open(state_file)?.read_to_string(&mut content)?;
    };
    // Replace non-breaking space '\u{A0}'  to normal space
    let content = content.replace('\u{A0}', " ");

    let state = NetworkState::new_from_yaml(&content)?;
    Ok(serde_yaml::to_string(&state)?)
}
