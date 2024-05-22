// SPDX-License-Identifier: Apache-2.0

#[cfg(feature = "query_apply")]
mod apply;
#[cfg(feature = "query_apply")]
mod checkpoint;
#[cfg(feature = "gen_conf")]
mod gen_conf;
#[cfg(feature = "query_apply")]
mod gen_diff;
mod logger;
#[cfg(feature = "query_apply")]
mod policy;
#[cfg(feature = "query_apply")]
mod query;
mod state;

use std::ffi::CString;

use libc::{c_char, c_int};
use nmstate::NmstateError;
use once_cell::sync::OnceCell;

use crate::logger::MemoryLogger;

#[cfg(feature = "query_apply")]
pub use crate::apply::nmstate_net_state_apply;
#[cfg(feature = "query_apply")]
pub use crate::checkpoint::{
    nmstate_checkpoint_commit, nmstate_checkpoint_rollback,
};
#[cfg(feature = "gen_conf")]
pub use crate::gen_conf::nmstate_generate_configurations;
#[cfg(feature = "query_apply")]
pub use crate::policy::nmstate_net_state_from_policy;
#[cfg(feature = "query_apply")]
pub use crate::query::nmstate_net_state_retrieve;

pub(crate) const NMSTATE_PASS: c_int = 0;
pub(crate) const NMSTATE_FAIL: c_int = 1;

static INSTANCE: OnceCell<MemoryLogger> = OnceCell::new();

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_cstring_free(cstring: *mut c_char) {
    unsafe {
        if !cstring.is_null() {
            drop(CString::from_raw(cstring));
        }
    }
}

pub(crate) fn init_logger() -> Result<&'static MemoryLogger, NmstateError> {
    match INSTANCE.get() {
        Some(l) => {
            l.add_consumer();
            Ok(l)
        }
        None => {
            if INSTANCE.set(MemoryLogger::new()).is_err() {
                return Err(NmstateError::new(
                    nmstate::ErrorKind::Bug,
                    "Failed to set once_sync for logger".to_string(),
                ));
            }
            if let Some(l) = INSTANCE.get() {
                if let Err(e) = log::set_logger(l) {
                    Err(NmstateError::new(
                        nmstate::ErrorKind::Bug,
                        format!("Failed to log::set_logger: {e}"),
                    ))
                } else {
                    l.add_consumer();
                    log::set_max_level(log::LevelFilter::Debug);
                    Ok(l)
                }
            } else {
                Err(NmstateError::new(
                    nmstate::ErrorKind::Bug,
                    "Failed to get logger from once_sync".to_string(),
                ))
            }
        }
    }
}
