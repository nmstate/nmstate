// SPDX-License-Identifier: Apache-2.0

use std::ffi::{CStr, CString};
use std::time::SystemTime;

use libc::{c_char, c_int};

use crate::{init_logger, NMSTATE_FAIL, NMSTATE_PASS};

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_generate_configurations(
    state: *const c_char,
    configs: *mut *mut c_char,
    log: *mut *mut c_char,
    err_kind: *mut *mut c_char,
    err_msg: *mut *mut c_char,
) -> c_int {
    assert!(!state.is_null());
    assert!(!configs.is_null());
    assert!(!log.is_null());
    assert!(!err_kind.is_null());
    assert!(!err_msg.is_null());

    unsafe {
        *log = std::ptr::null_mut();
        *configs = std::ptr::null_mut();
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

    let net_state = match nmstate::NetworkState::new_from_yaml(net_state_str) {
        Ok(n) => n,
        Err(e) => {
            unsafe {
                *err_msg = CString::new(e.msg()).unwrap().into_raw();
                *err_kind =
                    CString::new(format!("{}", &e.kind())).unwrap().into_raw();
            }
            return NMSTATE_FAIL;
        }
    };

    let input_is_json =
        serde_json::from_str::<serde_json::Value>(net_state_str).is_ok();
    let result = net_state.gen_conf();
    unsafe {
        *log = CString::new(logger.drain(now)).unwrap().into_raw();
    }
    match result {
        Ok(s) => {
            let serialize = if input_is_json {
                serde_json::to_string(&s).map_err(|e| {
                    nmstate::NmstateError::new(
                        nmstate::ErrorKind::Bug,
                        format!("Failed to convert state {s:?} to JSON: {e}"),
                    )
                })
            } else {
                serde_yaml::to_string(&s).map_err(|e| {
                    nmstate::NmstateError::new(
                        nmstate::ErrorKind::Bug,
                        format!("Failed to convert state {s:?} to YAML: {e}"),
                    )
                })
            };

            match serialize {
                Ok(cfgs) => unsafe {
                    *configs = CString::new(cfgs).unwrap().into_raw();
                    NMSTATE_PASS
                },
                Err(e) => unsafe {
                    *err_msg =
                        CString::new(e.msg().to_string()).unwrap().into_raw();
                    *err_kind =
                        CString::new(e.kind().to_string()).unwrap().into_raw();
                    NMSTATE_FAIL
                },
            }
        }
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
