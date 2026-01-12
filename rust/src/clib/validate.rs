// SPDX-License-Identifier: Apache-2.0

use std::ffi::{CStr, CString};

use libc::{c_char, c_int};

use crate::{
    NMSTATE_FAIL, NMSTATE_PASS, policy::c_str_to_net_policy,
    state::c_str_to_net_state,
};

#[allow(clippy::not_unsafe_ptr_arg_deref)]
#[unsafe(no_mangle)]
pub extern "C" fn nmstate_validate(
    state_or_policy: *const c_char,
    cur_state: *const c_char,
    err_kind: *mut *mut c_char,
    err_msg: *mut *mut c_char,
) -> c_int {
    assert!(!state_or_policy.is_null());
    assert!(!err_kind.is_null());
    assert!(!err_msg.is_null());

    unsafe {
        *err_kind = std::ptr::null_mut();
        *err_msg = std::ptr::null_mut();
    }

    let cur_state = if cur_state.is_null() {
        None
    } else {
        let cur_state_cstr = unsafe { CStr::from_ptr(cur_state) };
        if cur_state_cstr.to_str().map(|s| s.is_empty()) == Ok(true) {
            None
        } else {
            match c_str_to_net_state(cur_state, err_kind, err_msg) {
                Ok(s) => Some(s),
                Err(rc) => {
                    return rc;
                }
            }
        }
    };

    if let Ok(mut policy) =
        c_str_to_net_policy(state_or_policy, err_kind, err_msg)
    {
        policy.current = cur_state.clone();
        if let Err(e) = policy.validate() {
            unsafe {
                *err_msg =
                    CString::new(e.msg().to_string()).unwrap().into_raw();
                *err_kind =
                    CString::new(e.kind().to_string()).unwrap().into_raw();
            }
            return NMSTATE_FAIL;
        } else {
            return NMSTATE_PASS;
        }
    }

    // Try NetworkState again

    match c_str_to_net_state(state_or_policy, err_kind, err_msg) {
        Ok(state) => {
            if let Err(e) = state.validate(cur_state.as_ref()) {
                unsafe {
                    *err_msg =
                        CString::new(e.msg().to_string()).unwrap().into_raw();
                    *err_kind =
                        CString::new(e.kind().to_string()).unwrap().into_raw();
                }
                return NMSTATE_FAIL;
            }
        }
        Err(rc) => {
            return rc;
        }
    }

    NMSTATE_PASS
}
