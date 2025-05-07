// SPDX-License-Identifier: Apache-2.0

use libc::{c_char, c_int};

use crate::{init_logger, NMSTATE_FAIL, NMSTATE_PASS};

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_validate(
    state: *const c_char,
    policy: *const c_char,
    log: *mut *mut c_char,
    err_kind: *mut *mut c_char,
    err_msg: *mut *mut c_char,
) -> c_int {
    use std::ffi::{CStr, CString};
    use std::time::SystemTime;

    assert!(!state.is_null());
    assert!(!policy.is_null());
    assert!(!log.is_null());
    assert!(!err_kind.is_null());
    assert!(!err_msg.is_null());

    unsafe {
        *log = std::ptr::null_mut();
        *err_kind = std::ptr::null_mut();
        *err_msg = std::ptr::null_mut();
    }

    let now = SystemTime::now();
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

    let state_str = unsafe { CStr::from_ptr(state) }.to_string_lossy();
    let policy_str = unsafe { CStr::from_ptr(policy) }.to_string_lossy();

    let result = nmstate::validate(&state_str, &policy_str);

    unsafe {
        *log = CString::new(logger.drain(now)).unwrap().into_raw();
    }

    match result {
        Ok(()) => NMSTATE_PASS,
        Err(e) => {
            unsafe {
                *err_kind =
                    CString::new(format!("{}", e.kind())).unwrap().into_raw();
                *err_msg = CString::new(e.to_string()).unwrap().into_raw();
            }
            NMSTATE_FAIL
        }
    }
}
