// SPDX-License-Identifier: Apache-2.0

use std::{collections::HashMap, sync::LazyLock};

use log::warn;
use tokio::sync::{Mutex, MutexGuard};

use crate::{
    NmstateError,
    nm::{error::nm_error_to_nmstate, nm_dbus::NmApi},
};

// Wait maximum 60 seconds for rollback
pub(crate) const CHECKPOINT_ROLLBACK_TIMEOUT: u32 = 60;

// NetworkManager `NM_ROLLBACK_RESULT_OK`.
const NM_ROLLBACK_RESULT_OK: u32 = 0;

// Checkpoint creation fails while another checkpoint exists, but xfrm
// cleanup runs after that checkpoint is gone. Hold this across the whole
// NetworkManager apply, and across a later commit or rollback, so one
// apply cannot delete another apply's pre-created interfaces.
static NM_APPLY_LOCK: LazyLock<Mutex<()>> = LazyLock::new(|| Mutex::new(()));

pub(crate) async fn nm_apply_lock() -> MutexGuard<'static, ()> {
    NM_APPLY_LOCK.lock().await
}

fn rollback_results_ok(results: &HashMap<String, u32>) -> bool {
    results
        .values()
        .all(|result| *result == NM_ROLLBACK_RESULT_OK)
}

pub(crate) async fn nm_checkpoint_create(
    timeout: u32,
) -> Result<String, NmstateError> {
    let mut nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_create(timeout)
        .await
        .map_err(nm_error_to_nmstate)
}

pub(crate) async fn nm_checkpoint_rollback(
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let mut nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    let rollback_result = nm_api
        .checkpoint_rollback(checkpoint)
        .await
        .map_err(nm_error_to_nmstate);
    let rollback_succeeded =
        rollback_result.as_ref().is_ok_and(rollback_results_ok);
    let wait_succeeded = match nm_api
        .wait_checkpoint_rollback(CHECKPOINT_ROLLBACK_TIMEOUT)
        .await
    {
        Ok(()) => true,
        Err(e) => {
            warn!("{e}");
            false
        }
    };
    // Devices created for IPSec are outside the checkpoint. Remove them only
    // after every device rollback result is success and deactivation has
    // finished. A partial rollback can leave the VPN using the interface.
    if rollback_succeeded && wait_succeeded {
        super::query_apply::rollback_precreated_xfrm().await;
    } else {
        warn!(
            "leaving pre-created xfrm interfaces in place because checkpoint \
             rollback did not finish cleanly"
        );
    }
    rollback_result.map(|_| ())
}

pub(crate) async fn nm_checkpoint_destroy(
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let mut nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_destroy(checkpoint)
        .await
        .map_err(nm_error_to_nmstate)?;
    super::query_apply::discard_precreated_xfrm();
    Ok(())
}

pub(crate) async fn nm_checkpoint_timeout_extend(
    checkpoint: &str,
    added_time_sec: u32,
) -> Result<(), NmstateError> {
    let nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_timeout_extend(checkpoint, added_time_sec)
        .await
        .map_err(nm_error_to_nmstate)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn xfrm_cleanup_requires_every_rollback_result_ok() {
        assert!(rollback_results_ok(&HashMap::new()));

        let mut results = HashMap::new();
        results.insert("/org/freedesktop/NetworkManager/Devices/1".into(), 0);
        assert!(rollback_results_ok(&results));

        results.insert("/org/freedesktop/NetworkManager/Devices/2".into(), 3);
        assert!(!rollback_results_ok(&results));
    }
}
