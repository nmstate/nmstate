// SPDX-License-Identifier: Apache-2.0

use nmstate::NetworkState;
use std::io::Read;

use crate::error::CliError;

pub(crate) fn state_from_file(
    file_path: &str,
) -> Result<NetworkState, CliError> {
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
