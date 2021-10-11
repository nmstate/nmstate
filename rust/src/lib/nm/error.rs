use nm_dbus::NmError;

use crate::{ErrorKind, NmstateError};

pub(crate) fn nm_error_to_nmstate(nm_error: NmError) -> NmstateError {
    NmstateError::new(
        ErrorKind::Bug,
        format!(
            "{}: {} dbus: {:?}",
            nm_error.kind, nm_error.msg, nm_error.dbus_error
        ),
    )
}
