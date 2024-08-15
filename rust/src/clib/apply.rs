// SPDX-License-Identifier: Apache-2.0

use std::ffi::CString;
use std::time::SystemTime;

use libc::{c_char, c_int};

use crate::{
    init_logger,
    query::{
        NMSTATE_FLAG_KERNEL_ONLY, NMSTATE_FLAG_MEMORY_ONLY,
        NMSTATE_FLAG_NO_COMMIT, NMSTATE_FLAG_NO_VERIFY,
    },
    state::c_str_to_net_state,
    NMSTATE_FAIL, NMSTATE_PASS,
};

const NMSTATE_FLAG_VERBOSE_WHEN_RETRY: u32 = 1 << 9;

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_net_state_apply(
    flags: u32,
    state: *const c_char,
    rollback_timeout: u32,
    log: *mut *mut c_char,
    err_kind: *mut *mut c_char,
    err_msg: *mut *mut c_char,
) -> c_int {
    assert!(!log.is_null());
    assert!(!err_kind.is_null());
    assert!(!err_msg.is_null());

    unsafe {
        *log = std::ptr::null_mut();
        *err_kind = std::ptr::null_mut();
        *err_msg = std::ptr::null_mut();
    }

    if state.is_null() {
        return NMSTATE_PASS;
    }

    let logger = match init_logger() {
        Ok(l) => l,
        Err(e) => {
            unsafe {
                *err_msg = CString::new(format!("Failed to setup logger: {e}"))
                    .unwrap()
                    .into_raw();
            }
            return NMSTATE_FAIL;
        }
    };
    let now = SystemTime::now();

    let mut net_state = match c_str_to_net_state(state, err_kind, err_msg) {
        Ok(s) => s,
        Err(rc) => {
            return rc;
        }
    };

    if (flags & NMSTATE_FLAG_KERNEL_ONLY) > 0 {
        net_state.set_kernel_only(true);
    }

    if (flags & NMSTATE_FLAG_NO_VERIFY) > 0 {
        net_state.set_verify_change(false);
    }

    if (flags & NMSTATE_FLAG_NO_COMMIT) > 0 {
        net_state.set_commit(false);
    }

    if (flags & NMSTATE_FLAG_MEMORY_ONLY) > 0 {
        net_state.set_memory_only(true);
    }

    if (flags & NMSTATE_FLAG_VERBOSE_WHEN_RETRY) > 0 {
        net_state.set_verbose_log_when_retry(true);
    }

    net_state.set_timeout(rollback_timeout);

    let result = net_state.apply();
    unsafe {
        *log = CString::new(logger.drain(now)).unwrap().into_raw();
    }

    if let Err(e) = result {
        unsafe {
            *err_msg = CString::new(e.msg()).unwrap().into_raw();
            *err_kind =
                CString::new(format!("{}", &e.kind())).unwrap().into_raw();
        }
        NMSTATE_FAIL
    } else {
        NMSTATE_PASS
    }
}
