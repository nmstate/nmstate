// SPDX-License-Identifier: Apache-2.0

#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
#[allow(dead_code)]
pub enum ErrorKind {
    DbusConnectionError,
    CheckpointConflict,
    InvalidArgument,
    NotFound,
    IncompatibleReapply,
    Bug,
    Timeout,
    LoopbackIfaceNotSupported,
    Device(NmDeviceError),
    Manager(NmManagerError),
    Setting(NmSettingError),
    Connection(NmConnectionError),
}

#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
#[allow(dead_code)]
pub enum NmDeviceError {
    CreationFailed,
    InvalidConnection,
    IncompatibleConnection,
    NotActive,
    NotSoftware,
    NotAllowed,
    SpecificObjectNotFound,
    VersionIdMismatch,
    MissingDependencies,
    InvalidArgument,
    Unknown(String),
}

impl From<&str> for NmDeviceError {
    fn from(nm_err_kind: &str) -> Self {
        match nm_err_kind {
            "CreationFailed" => Self::CreationFailed,
            "InvalidConnection" => Self::InvalidConnection,
            "IncompatibleConnection" => Self::IncompatibleConnection,
            "NotActive" => Self::NotActive,
            "NotSoftware" => Self::NotSoftware,
            "NotAllowed" => Self::NotAllowed,
            "SpecificObjectNotFound" => Self::SpecificObjectNotFound,
            "VersionIdMismatch" => Self::VersionIdMismatch,
            "MissingDependencies" => Self::MissingDependencies,
            "InvalidArgument" => Self::InvalidArgument,
            _ => {
                log::warn!(
                    "Unknown error kind \
                    org.freedesktop.NetworkManager.Device.{nm_err_kind}"
                );
                Self::Unknown(nm_err_kind.to_string())
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
#[allow(dead_code)]
pub enum NmSettingError {
    Failed,
    PermissionDenied,
    NotSupported,
    InvalidConnection,
    ReadOnlyConnection,
    UuidExists,
    InvalidHostname,
    InvalidArguments,
    Unknown(String),
}

impl From<&str> for NmSettingError {
    fn from(nm_err_kind: &str) -> Self {
        match nm_err_kind {
            "Failed" => Self::Failed,
            "PermissionDenied" => Self::PermissionDenied,
            "NotSupported" => Self::NotSupported,
            "InvalidConnection" => Self::InvalidConnection,
            "ReadOnlyConnection" => Self::ReadOnlyConnection,
            "UuidExists" => Self::UuidExists,
            "InvalidHostname" => Self::InvalidHostname,
            "InvalidArguments" => Self::InvalidArguments,
            _ => {
                log::warn!(
                    "Unknown error kind \
                    org.freedesktop.NetworkManager.Settings.{nm_err_kind}"
                );
                Self::Unknown(nm_err_kind.to_string())
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
#[allow(dead_code)]
pub enum NmConnectionError {
    Failed,
    SettingNotFound,
    PropertyNotFound,
    PropertyNotSecret,
    MissingSetting,
    InvalidSetting,
    MissingProperty,
    InvalidProperty,
    Unknown(String),
}

impl From<&str> for NmConnectionError {
    fn from(nm_err_kind: &str) -> Self {
        match nm_err_kind {
            "Failed" => Self::Failed,
            "SettingNotFound" => Self::SettingNotFound,
            "PropertyNotFound" => Self::PropertyNotFound,
            "PropertyNotSecret" => Self::PropertyNotSecret,
            "MissingSetting" => Self::MissingSetting,
            "InvalidSetting" => Self::InvalidSetting,
            "MissingProperty" => Self::MissingProperty,
            "InvalidProperty" => Self::InvalidProperty,
            _ => {
                log::warn!(
                    "Unknown error kind org.freedesktop.NetworkManager.\
                    Settings.Connection.{nm_err_kind}"
                );
                Self::Unknown(nm_err_kind.to_string())
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
#[allow(dead_code)]
pub enum NmManagerError {
    Failed,
    PermissionDenied,
    UnknownConnection,
    UnknownDevice,
    ConnectionNotAvailable,
    ConnectionNotActive,
    ConnectionAlreadyActive,
    DependencyFailed,
    AlreadyAsleepOrAwake,
    UnknownLogLevel,
    UnknownLogDomain,
    InvalidArguments,
    MissingPlugin,
    Unknown(String),
}

impl From<&str> for NmManagerError {
    fn from(nm_err_kind: &str) -> Self {
        match nm_err_kind {
            "Failed" => Self::Failed,
            "PermissionDenied" => Self::PermissionDenied,
            "UnknownConnection" => Self::UnknownConnection,
            "UnknownDevice" => Self::UnknownDevice,
            "ConnectionNotAvailable" => Self::ConnectionNotAvailable,
            "ConnectionNotActive" => Self::ConnectionNotActive,
            "ConnectionAlreadyActive" => Self::ConnectionAlreadyActive,
            "DependencyFailed" => Self::DependencyFailed,
            "AlreadyAsleepOrAwake" => Self::AlreadyAsleepOrAwake,
            "UnknownLogLevel" => Self::UnknownLogLevel,
            "UnknownLogDomain" => Self::UnknownLogDomain,
            "InvalidArguments" => Self::InvalidArguments,
            "MissingPlugin" => Self::MissingPlugin,
            _ => {
                log::warn!(
                    "Unknown error kind \
                    org.freedesktop.NetworkManager.{nm_err_kind}"
                );
                Self::Unknown(nm_err_kind.to_string())
            }
        }
    }
}

#[cfg(feature = "query_apply")]
const NM_DBUS_ERR_PREFIX: &str = "org.freedesktop.NetworkManager.";

#[cfg(feature = "query_apply")]
fn parse_nm_dbus_error(nm_err_kind: &str, nm_err_msg: &str) -> NmError {
    if nm_err_kind.len() > NM_DBUS_ERR_PREFIX.len() {
        let sub_error_kind = &nm_err_kind[NM_DBUS_ERR_PREFIX.len()..];

        let error_kinds: Vec<&str> = sub_error_kind.split('.').collect();

        if error_kinds.len() >= 2 {
            let sub_error_kind = error_kinds[1..].join(".");
            match error_kinds[0] {
                "Device" => {
                    return NmError::new(
                        ErrorKind::Device(sub_error_kind.as_str().into()),
                        nm_err_msg.to_string(),
                    );
                }
                "Settings" => {
                    if error_kinds[1] == "Connection" {
                        return NmError::new(
                            ErrorKind::Connection(
                                sub_error_kind.as_str()["Connection.".len()..]
                                    .into(),
                            ),
                            nm_err_msg.to_string(),
                        );
                    } else {
                        return NmError::new(
                            ErrorKind::Setting(sub_error_kind.as_str().into()),
                            nm_err_msg.to_string(),
                        );
                    }
                }
                _ => {
                    log::warn!(
                        "Unknown NM error {}: {}",
                        nm_err_kind,
                        nm_err_msg
                    );
                }
            }
        } else {
            let mut err = NmError::new(
                ErrorKind::Manager(sub_error_kind.into()),
                nm_err_msg.to_string(),
            );
            // NM 1.42- are using NmManagerError::Failed when OVS plugin missing
            if err.kind == ErrorKind::Manager(NmManagerError::Failed)
                && err.msg.contains("plugin for 'ovs")
            {
                err.kind = ErrorKind::Manager(NmManagerError::MissingPlugin);
            }
            return err;
        }
    }
    NmError::new(ErrorKind::Bug, format!("{nm_err_kind}: {nm_err_msg}"))
}

impl std::fmt::Display for ErrorKind {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{self:?}")
    }
}

#[derive(Debug)]
pub struct NmError {
    pub kind: ErrorKind,
    pub msg: String,
}

impl NmError {
    pub fn new(kind: ErrorKind, msg: String) -> Self {
        Self { kind, msg }
    }
}

impl std::fmt::Display for NmError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{:?}:{}", self.kind, self.msg)
    }
}

#[cfg(feature = "query_apply")]
impl From<zbus::Error> for NmError {
    fn from(e: zbus::Error) -> Self {
        if let zbus::Error::MethodError(dbus_err_kind, dbus_err_msg, _) = &e {
            if dbus_err_kind.starts_with(NM_DBUS_ERR_PREFIX) {
                return parse_nm_dbus_error(
                    dbus_err_kind.as_str(),
                    if let Some(dbus_err_msg) = dbus_err_msg.as_ref() {
                        dbus_err_msg.as_str()
                    } else {
                        ""
                    },
                );
            }
        }

        log::warn!("Unknown DBUS error {:?}", e);

        Self {
            kind: ErrorKind::DbusConnectionError,
            msg: format!("{e}"),
        }
    }
}

#[cfg(feature = "query_apply")]
impl From<zbus::fdo::Error> for NmError {
    fn from(e: zbus::fdo::Error) -> Self {
        Self {
            kind: ErrorKind::Bug,
            msg: format!("zbus fdo error {e}"),
        }
    }
}

impl From<zvariant::Error> for NmError {
    fn from(e: zvariant::Error) -> Self {
        Self {
            kind: ErrorKind::Bug,
            msg: format!("zvariant error: {e:?}"),
        }
    }
}

impl From<std::io::Error> for NmError {
    fn from(e: std::io::Error) -> Self {
        Self::new(ErrorKind::Bug, format!("failed to write file: {e}"))
    }
}
