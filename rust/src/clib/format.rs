// SPDX-License-Identifier: Apache-2.0

use std::ffi::CString;

use libc::{c_char, c_int};

use crate::{
    state::{c_str_to_net_state, is_state_in_json},
    NMSTATE_FAIL, NMSTATE_PASS,
};

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[no_mangle]
pub extern "C" fn nmstate_net_state_format(
    state: *const c_char,
    formated_state: *mut *mut c_char,
    err_kind: *mut *mut c_char,
    err_msg: *mut *mut c_char,
) -> c_int {
    assert!(!state.is_null());
    assert!(!formated_state.is_null());
    assert!(!err_kind.is_null());
    assert!(!err_msg.is_null());

    unsafe {
        *formated_state = std::ptr::null_mut();
        *err_kind = std::ptr::null_mut();
        *err_msg = std::ptr::null_mut();
    }

    if state.is_null() {
        return NMSTATE_PASS;
    }

    let net_state = match c_str_to_net_state(state, err_kind, err_msg) {
        Ok(s) => s,
        Err(rc) => {
            return rc;
        }
    };

    let input_is_json = is_state_in_json(state);

    let serialize = if input_is_json {
        serde_json::to_string(&net_state).map_err(|e| {
            nmstate::NmstateError::new(
                nmstate::ErrorKind::Bug,
                format!("Failed to convert state {net_state:?} to JSON: {e}"),
            )
        })
    } else {
        serde_yaml::to_string(&net_state).map_err(|e| {
            nmstate::NmstateError::new(
                nmstate::ErrorKind::Bug,
                format!("Failed to convert state {net_state:?} to YAML: {e}"),
            )
        })
    };

    match serialize {
        Ok(s) => unsafe {
            *formated_state = CString::new(s).unwrap().into_raw();
            NMSTATE_PASS
        },
        Err(e) => unsafe {
            *err_msg = CString::new(e.msg().to_string()).unwrap().into_raw();
            *err_kind = CString::new(e.kind().to_string()).unwrap().into_raw();
            NMSTATE_FAIL
        },
    }
}
