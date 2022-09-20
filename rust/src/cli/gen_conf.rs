// SPDX-License-Identifier: Apache-2.0

use nmstate::NetworkState;

use crate::error::CliError;

pub(crate) fn gen_conf(file_path: &str) -> Result<String, CliError> {
    let fd = std::fs::File::open(file_path)?;
    let net_state: NetworkState = serde_yaml::from_reader(fd)?;
    let confs = net_state.gen_conf()?;
    let escaped_string = serde_yaml::to_string(&confs)?;
    Ok(escaped_string.replace("\\n", "\n\n"))
}
