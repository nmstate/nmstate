// SPDX-License-Identifier: Apache-2.0

use std::ffi::CString;

use libc::{c_char, c_int};

use crate::{
    state::{c_str_to_net_state, is_state_in_json},
    NMSTATE_FAIL, NMSTATE_PASS,
};

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_generate_differences(
    new_state: *const c_char,
    old_state: *const c_char,
    diff_state: *mut *mut c_char,
    err_kind: *mut *mut c_char,
    err_msg: *mut *mut c_char,
) -> c_int {
    assert!(!new_state.is_null());
    assert!(!old_state.is_null());
    assert!(!diff_state.is_null());
    assert!(!err_kind.is_null());
    assert!(!err_msg.is_null());

    unsafe {
        *diff_state = std::ptr::null_mut();
        *err_kind = std::ptr::null_mut();
        *err_msg = std::ptr::null_mut();
    }

    if new_state.is_null() {
        return NMSTATE_PASS;
    }

    let new_net_state = match c_str_to_net_state(new_state, err_kind, err_msg) {
        Ok(s) => s,
        Err(rc) => {
            return rc;
        }
    };
    let old_net_state = match c_str_to_net_state(old_state, err_kind, err_msg) {
        Ok(s) => s,
        Err(rc) => {
            return rc;
        }
    };

    let input_is_json = is_state_in_json(new_state);

    let result = new_net_state.gen_diff(&old_net_state);
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
                Ok(diff) => unsafe {
                    *diff_state = CString::new(diff).unwrap().into_raw();
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
