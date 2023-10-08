// SPDX-License-Identifier: Apache-2.0

use crate::{error::CliError, state::state_from_file};

pub(crate) fn format(state_file: &str) -> Result<String, CliError> {
    Ok(serde_yaml::to_string(&state_from_file(state_file)?)?)
}
