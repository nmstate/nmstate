// SPDX-License-Identifier: Apache-2.0

use crate::nm::nm_dbus::{
    ErrorKind as NmErrorKind, NmConnectionError, NmError, NmManagerError,
    NmSettingError,
};

use crate::{ErrorKind, NmstateError};

pub(crate) fn nm_error_to_nmstate(nm_error: NmError) -> NmstateError {
    match nm_error.kind {
        NmErrorKind::Manager(NmManagerError::MissingPlugin) => {
            NmstateError::new(ErrorKind::DependencyError, nm_error.to_string())
        }
        NmErrorKind::Manager(NmManagerError::PermissionDenied) => {
            if nm_error.msg.starts_with("Not authorized") {
                NmstateError::new(
                    ErrorKind::PermissionError,
                    nm_error.to_string(),
                )
            } else {
                NmstateError::new(
                    ErrorKind::Bug,
                    format!("{}: {}", nm_error.kind, nm_error.msg),
                )
            }
        }
        NmErrorKind::Setting(NmSettingError::PermissionDenied) => {
            NmstateError::new(ErrorKind::PermissionError, nm_error.to_string())
        }
        NmErrorKind::Connection(NmConnectionError::InvalidSetting) => {
            NmstateError::new(
                ErrorKind::DependencyError,
                format!(
                    "Please upgrade NetworkManager for specified interface \
                    type: {nm_error}"
                ),
            )
        }
        NmErrorKind::Connection(_) => {
            NmstateError::new(ErrorKind::InvalidArgument, nm_error.to_string())
        }
        _ => NmstateError::new(
            ErrorKind::Bug,
            format!("{}: {}", nm_error.kind, nm_error.msg),
        ),
    }
}
