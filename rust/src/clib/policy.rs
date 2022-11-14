// SPDX-License-Identifier: Apache-2.0

use std::convert::TryFrom;
use std::ffi::{CStr, CString};
use std::time::SystemTime;

use libc::{c_char, c_int};
use nmstate::{NetworkPolicy, NetworkState};

use crate::{init_logger, NMSTATE_FAIL, NMSTATE_PASS};

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_net_state_from_policy(
    policy: *const c_char,
    current_state: *const c_char,
    state: *mut *mut c_char,
    log: *mut *mut c_char,
    err_kind: *mut *mut c_char,
    err_msg: *mut *mut c_char,
) -> c_int {
    assert!(!policy.is_null());
    assert!(!state.is_null());
    assert!(!log.is_null());
    assert!(!err_kind.is_null());
    assert!(!err_msg.is_null());

    unsafe {
        *state = std::ptr::null_mut();
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
                *err_msg =
                    CString::new(format!("Failed to setup logger: {}", e))
                        .unwrap()
                        .into_raw();
            }
            return NMSTATE_FAIL;
        }
    };
    let now = SystemTime::now();

    let current = if current_state.is_null() {
        None
    } else {
        match deserilize_from_c_char::<NetworkState>(
            current_state,
            err_kind,
            err_msg,
        ) {
            Some(c) => Some(c),
            None => {
                unsafe {
                    *log = CString::new(logger.drain(now)).unwrap().into_raw();
                }
                return NMSTATE_FAIL;
            }
        }
    };

    let mut policy = match deserilize_from_c_char::<NetworkPolicy>(
        policy, err_kind, err_msg,
    ) {
        Some(p) => p,
        None => {
            unsafe {
                *log = CString::new(logger.drain(now)).unwrap().into_raw();
            }
            return NMSTATE_FAIL;
        }
    };
    policy.current = current;

    let result = NetworkState::try_from(policy);
    unsafe {
        *log = CString::new(logger.drain(now)).unwrap().into_raw();
    }

    match result {
        Ok(s) => match serde_json::to_string(&s) {
            Ok(state_str) => unsafe {
                *state = CString::new(state_str).unwrap().into_raw();
                NMSTATE_PASS
            },
            Err(e) => unsafe {
                *err_msg = CString::new(format!(
                    "serde_json::to_string failure: {}",
                    e
                ))
                .unwrap()
                .into_raw();
                *err_kind =
                    CString::new(format!("{}", nmstate::ErrorKind::Bug))
                        .unwrap()
                        .into_raw();
                NMSTATE_FAIL
            },
        },
        Err(e) => {
            unsafe {
                *err_msg = CString::new(e.msg()).unwrap().into_raw();
                *err_kind =
                    CString::new(format!("{}", &e.kind())).unwrap().into_raw();
            }
            NMSTATE_FAIL
        }
    }
}

fn deserilize_from_c_char<T>(
    content: *const c_char,
    err_kind: *mut *mut c_char,
    err_msg: *mut *mut c_char,
) -> Option<T>
where
    T: for<'de> serde::Deserialize<'de>,
{
    let content_cstr = unsafe { CStr::from_ptr(content) };

    let content_str = match content_cstr.to_str() {
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
            return None;
        }
    };

    match serde_json::from_str(content_str) {
        Ok(n) => Some(n),
        Err(e) => {
            unsafe {
                *err_msg = CString::new(e.to_string()).unwrap().into_raw();
                *err_kind = CString::new("InvalidArgument").unwrap().into_raw();
            }
            None
        }
    }
}
