// SPDX-License-Identifier: Apache-2.0

use std::fs;
use std::io::Write;
use std::path::PathBuf;

use crate::{ErrorKind, NetworkState, NmstateError};

use super::timeout::cancel_timeout_watchdog;

const KERNEL_CHECKPOINT_PREFIX: &str = "kernel:";
const DEFAULT_CHECKPOINT_DIR: &str = "/run/nmstate/checkpoints";
const CHECKPOINT_DIR_ENV: &str = "NMSTATE_CHECKPOINT_DIR";

fn get_checkpoint_dir() -> PathBuf {
    PathBuf::from(
        std::env::var(CHECKPOINT_DIR_ENV)
            .unwrap_or_else(|_| DEFAULT_CHECKPOINT_DIR.to_string()),
    )
}

/// Get the file path for a checkpoint ID.
pub(crate) fn get_checkpoint_path(checkpoint_id: &str) -> PathBuf {
    let filename = checkpoint_id
        .strip_prefix(KERNEL_CHECKPOINT_PREFIX)
        .unwrap_or(checkpoint_id);
    get_checkpoint_dir().join(format!("{}.yaml", filename))
}

fn ensure_checkpoint_dir() -> Result<(), NmstateError> {
    let dir = get_checkpoint_dir();
    if !dir.exists() {
        fs::create_dir_all(&dir).map_err(|e| {
            NmstateError::new(
                ErrorKind::Bug,
                format!(
                    "Failed to create checkpoint directory {}: {}",
                    dir.display(),
                    e
                ),
            )
        })?;
    }
    Ok(())
}

/// Create a kernel checkpoint storing the revert state to a file.
/// Returns the checkpoint ID with "kernel:" prefix.
pub(crate) fn kernel_checkpoint_create(
    revert_state: NetworkState,
) -> Result<String, NmstateError> {
    ensure_checkpoint_dir()?;

    let uuid = uuid::Uuid::new_v4();
    let id = format!("{}{}", KERNEL_CHECKPOINT_PREFIX, uuid);
    let path = get_checkpoint_path(&id);

    let yaml = serde_yaml::to_string(&revert_state).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!("Failed to serialize checkpoint state: {}", e),
        )
    })?;

    let mut file = fs::File::create(&path).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!(
                "Failed to create checkpoint file {}: {}",
                path.display(),
                e
            ),
        )
    })?;

    file.write_all(yaml.as_bytes()).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!(
                "Failed to write checkpoint file {}: {}",
                path.display(),
                e
            ),
        )
    })?;

    log::debug!("Saved kernel checkpoint to {}", path.display());
    Ok(id)
}

/// Get the revert state for a kernel checkpoint from file.
/// The checkpoint ID can be with or without the "kernel:" prefix.
pub(crate) fn kernel_checkpoint_get(
    checkpoint_id: &str,
) -> Result<Option<NetworkState>, NmstateError> {
    let id = if checkpoint_id.starts_with(KERNEL_CHECKPOINT_PREFIX) {
        checkpoint_id.to_string()
    } else {
        format!("{}{}", KERNEL_CHECKPOINT_PREFIX, checkpoint_id)
    };

    let path = get_checkpoint_path(&id);

    if !path.exists() {
        return Ok(None);
    }

    let content = fs::read_to_string(&path).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!(
                "Failed to read checkpoint file {}: {}",
                path.display(),
                e
            ),
        )
    })?;

    let state: NetworkState =
        serde_yaml::from_str(&content).map_err(|e| {
            NmstateError::new(
                ErrorKind::Bug,
                format!(
                    "Failed to deserialize checkpoint file {}: {}",
                    path.display(),
                    e
                ),
            )
        })?;

    log::debug!("Loaded kernel checkpoint from {}", path.display());
    Ok(Some(state))
}

/// Destroy (commit) a kernel checkpoint, removing the file
/// and cancelling any timeout watchdog.
/// The checkpoint ID can be with or without the "kernel:" prefix.
pub(crate) fn kernel_checkpoint_destroy(checkpoint_id: &str) {
    let id = if checkpoint_id.starts_with(KERNEL_CHECKPOINT_PREFIX) {
        checkpoint_id.to_string()
    } else {
        format!("{}{}", KERNEL_CHECKPOINT_PREFIX, checkpoint_id)
    };

    let path = get_checkpoint_path(&id);

    // Cancel timeout watchdog before removing checkpoint file
    cancel_timeout_watchdog(&path);

    if path.exists() {
        if let Err(e) = fs::remove_file(&path) {
            log::warn!(
                "Failed to remove checkpoint file {}: {}",
                path.display(),
                e
            );
        } else {
            log::debug!("Removed kernel checkpoint file {}", path.display());
        }
    }
}

/// Check if a checkpoint ID is a kernel checkpoint.
pub(crate) fn is_kernel_checkpoint(checkpoint_id: &str) -> bool {
    checkpoint_id.starts_with(KERNEL_CHECKPOINT_PREFIX)
}
