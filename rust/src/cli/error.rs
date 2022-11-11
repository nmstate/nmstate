// SPDX-License-Identifier: Apache-2.0

use nmstate::NmstateError;

pub(crate) const DEFAULT_ERROR_CODE: i32 = 1;
pub(crate) const EX_DATAERR: i32 = 65;
const EX_USAGE: i32 = 64;

#[derive(Debug, Default)]
pub(crate) struct CliError {
    pub(crate) code: i32,
    pub(crate) error_msg: String,
}

impl From<&str> for CliError {
    fn from(msg: &str) -> Self {
        Self {
            code: DEFAULT_ERROR_CODE,
            error_msg: msg.into(),
        }
    }
}

impl From<String> for CliError {
    fn from(error_msg: String) -> Self {
        Self {
            code: DEFAULT_ERROR_CODE,
            error_msg,
        }
    }
}

impl std::fmt::Display for CliError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.error_msg)
    }
}

impl From<std::io::Error> for CliError {
    fn from(e: std::io::Error) -> Self {
        Self {
            code: DEFAULT_ERROR_CODE,
            error_msg: format!("std::io::Error: {e}"),
        }
    }
}

impl From<NmstateError> for CliError {
    fn from(e: NmstateError) -> Self {
        Self {
            code: DEFAULT_ERROR_CODE,
            error_msg: format!("NmstateError: {e}"),
        }
    }
}

impl From<serde_yaml::Error> for CliError {
    fn from(e: serde_yaml::Error) -> Self {
        Self {
            code: EX_DATAERR,
            error_msg: format!("serde_yaml::Error: {e}"),
        }
    }
}

impl From<clap::Error> for CliError {
    fn from(e: clap::Error) -> Self {
        Self {
            code: EX_USAGE,
            error_msg: format!("clap::Error {e}"),
        }
    }
}

impl From<serde_json::Error> for CliError {
    fn from(e: serde_json::Error) -> Self {
        Self {
            code: EX_DATAERR,
            error_msg: format!("serde_json::Error {e}"),
        }
    }
}
