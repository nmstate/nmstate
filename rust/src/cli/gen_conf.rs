// SPDX-License-Identifier: Apache-2.0

use std::io::Read;

use nmstate::NetworkState;

use crate::error::CliError;

pub(crate) fn gen_conf(file_path: &str) -> Result<String, CliError> {
    let mut fd = std::fs::File::open(file_path)?;
    let mut content = String::new();
    // Replace non-breaking space '\u{A0}'  to normal space
    fd.read_to_string(&mut content)?;
    let content = content.replace('\u{A0}', " ");
    let net_state: NetworkState = serde_yaml::from_str(&content)?;
    let confs = net_state.gen_conf()?;
    let escaped_string = serde_yaml::to_string(&confs)?;
    Ok(escaped_string.replace("\\n", "\n\n"))
}
