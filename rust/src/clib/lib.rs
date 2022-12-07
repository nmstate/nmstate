// Copyright 2021 Red Hat, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

use libc::{c_char, c_int};
use std::ffi::{CStr, CString};

const NMSTATE_FLAG_KERNEL_ONLY: u32 = 1 << 1;
const NMSTATE_FLAG_NO_VERIFY: u32 = 1 << 2;
const NMSTATE_FLAG_INCLUDE_STATUS_DATA: u32 = 1 << 3;
const NMSTATE_FLAG_INCLUDE_SECRETS: u32 = 1 << 4;
const NMSTATE_FLAG_NO_COMMIT: u32 = 1 << 5;
// TODO
// const NMSTATE_FLAG_MEMORY_ONLY: u32 = 1 << 6;

const NMSTATE_PASS: c_int = 0;
const NMSTATE_FAIL: c_int = 1;

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_net_state_retrieve(
    flags: u32,
    state: *mut *mut c_char,
    log: *mut *mut c_char,
    err_kind: *mut *mut c_char,
    err_msg: *mut *mut c_char,
) -> c_int {
    assert!(!state.is_null());
    assert!(!log.is_null());
    assert!(!err_kind.is_null());
    assert!(!err_msg.is_null());

    unsafe {
        *log = std::ptr::null_mut();
        *state = std::ptr::null_mut();
        *err_kind = std::ptr::null_mut();
        *err_msg = std::ptr::null_mut();
    }

    let mut net_state = nmstate::NetworkState::new();
    if (flags & NMSTATE_FLAG_KERNEL_ONLY) > 0 {
        net_state.set_kernel_only(true);
    }

    if (flags & NMSTATE_FLAG_INCLUDE_STATUS_DATA) > 0 {
        net_state.set_include_status_data(true);
    }

    if (flags & NMSTATE_FLAG_INCLUDE_SECRETS) > 0 {
        net_state.set_include_secrets(true);
    }

    // TODO: save log to the output pointer

    match net_state.retrieve() {
        Ok(s) => match serde_json::to_string(&s) {
            Ok(state_str) => unsafe {
                *state = CString::new(state_str).unwrap().into_raw();
                NMSTATE_PASS
            },
            Err(e) => unsafe {
                *err_msg =
                    CString::new(format!("serde_json::to_string failure: {e}"))
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

    let net_state_cstr = unsafe { CStr::from_ptr(state) };

    let net_state_str = match net_state_cstr.to_str() {
        Ok(s) => s,
        Err(e) => {
            unsafe {
                *err_msg = CString::new(format!(
                    "Error on converting C char to rust str: {e}"
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
    };

    let mut net_state =
        match nmstate::NetworkState::new_from_json(net_state_str) {
            Ok(n) => n,
            Err(e) => {
                unsafe {
                    *err_msg = CString::new(e.msg()).unwrap().into_raw();
                    *err_kind = CString::new(format!("{}", &e.kind()))
                        .unwrap()
                        .into_raw();
                }
                return NMSTATE_FAIL;
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

    net_state.set_timeout(rollback_timeout);

    // TODO: save log to the output pointer

    if let Err(e) = net_state.apply() {
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

    let mut checkpoint_str = "";
    if !checkpoint.is_null() {
        let checkpoint_cstr = unsafe { CStr::from_ptr(checkpoint) };
        checkpoint_str = match checkpoint_cstr.to_str() {
            Ok(s) => s,
            Err(e) => {
                unsafe {
                    *err_msg = CString::new(format!(
                        "Error on converting C char to rust str: {e}"
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

    if let Err(e) = nmstate::NetworkState::checkpoint_commit(checkpoint_str) {
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

    let mut checkpoint_str = "";
    if !checkpoint.is_null() {
        let checkpoint_cstr = unsafe { CStr::from_ptr(checkpoint) };
        checkpoint_str = match checkpoint_cstr.to_str() {
            Ok(s) => s,
            Err(e) => {
                unsafe {
                    *err_msg = CString::new(format!(
                        "Error on converting C char to rust str: {e}"
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

    if let Err(e) = nmstate::NetworkState::checkpoint_rollback(checkpoint_str) {
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
pub extern "C" fn nmstate_net_state_free(state: *mut c_char) {
    unsafe {
        if !state.is_null() {
            drop(CString::from_raw(state));
        }
    }
}

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_log_free(log: *mut c_char) {
    unsafe {
        if !log.is_null() {
            drop(CString::from_raw(log));
        }
    }
}

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_err_kind_free(err_kind: *mut c_char) {
    unsafe {
        if !err_kind.is_null() {
            drop(CString::from_raw(err_kind));
        }
    }
}

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_err_msg_free(err_msg: *mut c_char) {
    unsafe {
        if !err_msg.is_null() {
            drop(CString::from_raw(err_msg));
        }
    }
}

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_checkpoint_free(checkpoint: *mut c_char) {
    unsafe {
        if !checkpoint.is_null() {
            drop(CString::from_raw(checkpoint));
        }
    }
}
