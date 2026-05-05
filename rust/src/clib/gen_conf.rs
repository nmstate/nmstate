// SPDX-License-Identifier: Apache-2.0

use std::{ffi::CString, time::SystemTime};

use libc::{c_char, c_int};

use crate::{
    NMSTATE_FAIL, NMSTATE_PASS, init_logger,
    state::{c_str_to_net_state, is_state_in_json},
};

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[unsafe(no_mangle)]
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

    let net_state = match c_str_to_net_state(state, err_kind, err_msg) {
        Ok(n) => n,
        Err(rc) => {
            return rc;
        }
    };

    let input_is_json = is_state_in_json(state);
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
                    CString::new(format!("{}", e.kind())).unwrap().into_raw();
            }
            NMSTATE_FAIL
        }
    }
}
