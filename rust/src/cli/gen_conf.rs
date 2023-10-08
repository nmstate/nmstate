// SPDX-License-Identifier: Apache-2.0

use crate::{error::CliError, state::state_from_file};

pub(crate) fn gen_conf(file_path: &str) -> Result<String, CliError> {
    let net_state = state_from_file(file_path)?;
    let confs = net_state.gen_conf()?;
    let escaped_string = serde_yaml::to_string(&confs)?;
    Ok(escaped_string.replace("\\n", "\n\n"))
}
