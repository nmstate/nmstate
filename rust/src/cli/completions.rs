// SPDX-License-Identifier: Apache-2.0

use clap_complete::Shell;

use crate::{APP_NAME, error::CliError};

pub(crate) fn completions(
    shell: Shell,
    app: &mut clap::Command,
) -> Result<String, CliError> {
    let mut buf: Vec<u8> = Vec::new();
    clap_complete::generate(shell, app, APP_NAME, &mut buf);
    let script = String::from_utf8(buf).map_err(|e| {
        CliError::from(format!("Failed to generate {shell} completion: {e}"))
    })?;
    // print_result_and_exit() appends a newline
    Ok(script.trim_end().to_string())
}
