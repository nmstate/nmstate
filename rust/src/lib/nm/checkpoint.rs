use log::warn;
use nm_dbus::NmApi;

use crate::{nm::error::nm_error_to_nmstate, NmstateError};

// Wait maximum 30 seconds for rollback
const CHECKPOINT_ROLLBACK_TIMEOUT: u32 = 30;

pub(crate) fn nm_checkpoint_create() -> Result<String, NmstateError> {
    let nm_api = NmApi::new().map_err(nm_error_to_nmstate)?;
    nm_api.checkpoint_create().map_err(nm_error_to_nmstate)
}

pub(crate) fn nm_checkpoint_rollback(
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let nm_api = NmApi::new().map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_rollback(checkpoint)
        .map_err(nm_error_to_nmstate)?;
    if let Err(e) = nm_api.wait_checkpoint_rollback(CHECKPOINT_ROLLBACK_TIMEOUT)
    {
        warn!("{}", e);
    }
    Ok(())
}

pub(crate) fn nm_checkpoint_destroy(
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let nm_api = NmApi::new().map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_destroy(checkpoint)
        .map_err(nm_error_to_nmstate)
}

pub(crate) fn nm_checkpoint_timeout_extend(
    checkpoint: &str,
    added_time_sec: u32,
) -> Result<(), NmstateError> {
    let nm_api = NmApi::new().map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_timeout_extend(checkpoint, added_time_sec)
        .map_err(nm_error_to_nmstate)
}
