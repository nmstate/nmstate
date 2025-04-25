// SPDX-License-Identifier: Apache-2.0

use std::io::Read;

#[cfg(feature = "query_apply")]
use nmstate::NetworkPolicy;
use nmstate::NetworkState;

use crate::error::CliError;

pub(crate) enum NetworkStateOrPolicy {
    State(NetworkState),
    #[cfg(feature = "query_apply")]
    Policy(NetworkPolicy),
}

#[cfg(feature = "query_apply")]
impl TryFrom<NetworkStateOrPolicy> for NetworkState {
    type Error = CliError;
    fn try_from(value: NetworkStateOrPolicy) -> Result<Self, Self::Error> {
        match value {
            NetworkStateOrPolicy::Policy(policy) => {
                Ok(NetworkState::try_from(policy)?)
            }
            NetworkStateOrPolicy::State(state) => Ok(state),
        }
    }
}

#[cfg(not(feature = "query_apply"))]
impl TryFrom<NetworkStateOrPolicy> for NetworkState {
    type Error = CliError;
    fn try_from(value: NetworkStateOrPolicy) -> Result<Self, Self::Error> {
        match value {
            NetworkStateOrPolicy::State(state) => Ok(state),
        }
    }
}

pub(crate) fn state_from_file(
    file_path: &str,
) -> Result<NetworkState, CliError> {
    NetworkState::try_from(state_or_policy_from_file(file_path)?)
}

#[cfg(feature = "query_apply")]
pub(crate) fn state_from_fd<R>(fd: &mut R) -> Result<NetworkState, CliError>
where
    R: Read,
{
    NetworkState::try_from(state_or_policy_from_fd(fd)?)
}

pub(crate) fn state_or_policy_from_file(
    file_path: &str,
) -> Result<NetworkStateOrPolicy, CliError> {
    if file_path == "-" {
        state_or_policy_from_fd(&mut std::io::stdin())
    } else {
        state_or_policy_from_fd(&mut std::fs::File::open(file_path)?)
    }
}

#[cfg(not(feature = "query_apply"))]
pub(crate) fn state_or_policy_from_fd<R>(
    fd: &mut R,
) -> Result<NetworkStateOrPolicy, CliError>
where
    R: Read,
{
    let mut content = String::new();
    // Replace non-breaking space '\u{A0}'  to normal space
    fd.read_to_string(&mut content)?;
    let content = content.replace('\u{A0}', " ");

    match serde_yaml::from_str(&content) {
        Ok(s) => Ok(NetworkStateOrPolicy::State(s)),
        Err(e) => Err(CliError::from(format!(
            "Provide file is not valid NetworkState: {e}"
        ))),
    }
}

#[cfg(feature = "query_apply")]
pub(crate) fn state_or_policy_from_fd<R>(
    fd: &mut R,
) -> Result<NetworkStateOrPolicy, CliError>
where
    R: Read,
{
    let mut content = String::new();
    // Replace non-breaking space '\u{A0}'  to normal space
    fd.read_to_string(&mut content)?;
    let content = content.replace('\u{A0}', " ");

    match serde_yaml::from_str(&content) {
        Ok(s) => Ok(NetworkStateOrPolicy::State(s)),
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
            Ok(NetworkStateOrPolicy::Policy(net_policy))
        }
    }
}
