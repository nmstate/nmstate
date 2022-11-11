// SPDX-License-Identifier: Apache-2.0

use std::ffi::{CStr, CString};
use std::time::SystemTime;

use libc::{c_char, c_int};

use crate::{init_logger, NMSTATE_FAIL, NMSTATE_PASS};

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_checkpoint_commit(
    checkpoint: *const c_char,
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

    let mut checkpoint_str = "";
    if !checkpoint.is_null() {
        let checkpoint_cstr = unsafe { CStr::from_ptr(checkpoint) };
        checkpoint_str = match checkpoint_cstr.to_str() {
            Ok(s) => s,
            Err(e) => {
                unsafe {
                    *err_msg = CString::new(format!(
                        "Error on converting C char to rust str: {}",
                        e
                    ))
                    .unwrap()
                    .into_raw();
                    *err_kind = CString::new(format!(
                        "{}",
                        nmstate::ErrorKind::InvalidArgument
                    ))
                    .unwrap()
                    .into_raw();
                }
                return NMSTATE_FAIL;
            }
        }
    }

    let result = nmstate::NetworkState::checkpoint_commit(checkpoint_str);
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

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_checkpoint_rollback(
    checkpoint: *const c_char,
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

    let mut checkpoint_str = "";
    if !checkpoint.is_null() {
        let checkpoint_cstr = unsafe { CStr::from_ptr(checkpoint) };
        checkpoint_str = match checkpoint_cstr.to_str() {
            Ok(s) => s,
            Err(e) => {
                unsafe {
                    *err_msg = CString::new(format!(
                        "Error on converting C char to rust str: {}",
                        e
                    ))
                    .unwrap()
                    .into_raw();
                    *err_kind = CString::new(format!(
                        "{}",
                        nmstate::ErrorKind::InvalidArgument
                    ))
                    .unwrap()
                    .into_raw();
                }
                return NMSTATE_FAIL;
            }
        }
    }

    // TODO: save log to the output pointer
    let result = nmstate::NetworkState::checkpoint_rollback(checkpoint_str);
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
