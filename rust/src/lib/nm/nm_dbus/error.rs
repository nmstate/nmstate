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
        write!(f, "{}", self.msg)
    }
}

#[cfg(feature = "query_apply")]
impl From<zbus::Error> for NmError {
    fn from(e: zbus::Error) -> Self {
        Self {
            kind: ErrorKind::DbusConnectionError,
            msg: format!("{e}"),
        }
    }
}

impl From<zvariant::Error> for NmError {
    fn from(e: zvariant::Error) -> Self {
        Self {
            kind: ErrorKind::Bug,
            msg: format!("{e}"),
        }
    }
}

impl From<std::io::Error> for NmError {
    fn from(e: std::io::Error) -> Self {
        Self::new(ErrorKind::Bug, format!("failed to write file: {e}"))
    }
}
