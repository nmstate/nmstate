// SPDX-License-Identifier: Apache-2.0

use std::io::Read;

#[cfg(feature = "query_apply")]
use nmstate::NetworkPolicy;
use nmstate::NetworkState;

use crate::error::CliError;

pub(crate) fn state_from_file(
    file_path: &str,
) -> Result<NetworkState, CliError> {
    if file_path == "-" {
        state_from_fd(&mut std::io::stdin())
    } else {
        state_from_fd(&mut std::fs::File::open(file_path)?)
    }
}

#[cfg(not(feature = "query_apply"))]
pub(crate) fn state_from_fd<R>(fd: &mut R) -> Result<NetworkState, CliError>
where
    R: Read,
{
    let mut content = String::new();
    // Replace non-breaking space '\u{A0}'  to normal space
    fd.read_to_string(&mut content)?;
    let content = content.replace('\u{A0}', " ");

    match serde_yaml::from_str(&content) {
        Ok(s) => Ok(s),
        Err(e) => Err(CliError::from(format!(
            "Provide file is not valid NetworkState: {e}"
        ))),
    }
}

#[cfg(feature = "query_apply")]
pub(crate) fn state_from_fd<R>(fd: &mut R) -> Result<NetworkState, CliError>
where
    R: Read,
{
    let mut content = String::new();
    // Replace non-breaking space '\u{A0}'  to normal space
    fd.read_to_string(&mut content)?;
    let content = content.replace('\u{A0}', " ");

    match serde_yaml::from_str(&content) {
        Ok(s) => Ok(s),
        Err(state_error) => {
            // Try NetworkPolicy
            let net_policy: NetworkPolicy = match serde_yaml::from_str(&content)
            {
                Ok(p) => p,
                Err(policy_error) => {
                    let e = if content.contains("desiredState")
                        || content.contains("desired")
                    {
                        policy_error
                    } else {
                        state_error
                    };
                    return Err(CliError::from(format!(
                        "Provide file is not valid NetworkState or \
                        NetworkPolicy: {e}"
                    )));
                }
            };
            Ok(NetworkState::try_from(net_policy)?)
        }
    }
}
