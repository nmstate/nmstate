use crate::nm::{nm_checkpoint_destroy, nm_checkpoint_rollback};

use crate::NmstateError;

pub fn checkpoint_rollback(checkpoint: &str) -> Result<(), NmstateError> {
    nm_checkpoint_rollback(checkpoint)
}

pub fn checkpoint_commit(checkpoint: &str) -> Result<(), NmstateError> {
    nm_checkpoint_destroy(checkpoint)
}
