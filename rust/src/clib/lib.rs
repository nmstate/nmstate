// SPDX-License-Identifier: Apache-2.0

#[cfg(feature = "query_apply")]
mod apply;
#[cfg(feature = "query_apply")]
mod checkpoint;
mod format;
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
#[cfg(feature = "query_apply")]
mod validate;

use std::{ffi::CString, sync::OnceLock};

use libc::{c_char, c_int};
use nmstate::NmstateError;

#[cfg(feature = "query_apply")]
pub use crate::apply::nmstate_net_state_apply;
#[cfg(feature = "query_apply")]
pub use crate::checkpoint::{
    nmstate_checkpoint_commit, nmstate_checkpoint_rollback,
};
#[cfg(feature = "gen_conf")]
pub use crate::gen_conf::nmstate_generate_configurations;
use crate::logger::MemoryLogger;
#[cfg(feature = "query_apply")]
pub use crate::policy::nmstate_net_state_from_policy;
#[cfg(feature = "query_apply")]
pub use crate::query::nmstate_net_state_retrieve;
#[cfg(feature = "query_apply")]
pub use crate::validate::nmstate_validate;

pub(crate) const NMSTATE_PASS: c_int = 0;
pub(crate) const NMSTATE_FAIL: c_int = 1;

pub use crate::format::nmstate_net_state_format;

static INSTANCE: OnceLock<MemoryLogger> = OnceLock::new();

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[unsafe(no_mangle)]
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
            let l = INSTANCE.get_or_init(MemoryLogger::new);
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
        }
    }
}
