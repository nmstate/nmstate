// SPDX-License-Identifier: Apache-2.0

use std::ffi::{CStr, CString};

use libc::{c_char, c_int};
use nmstate::{ErrorKind, NetworkState};

use crate::NMSTATE_FAIL;

pub(crate) fn c_str_to_net_state(
    state: *const c_char,
    err_kind: *mut *mut c_char,
    err_msg: *mut *mut c_char,
) -> Result<NetworkState, c_int> {
    let net_state_cstr = unsafe { CStr::from_ptr(state) };
    let net_state_str = net_state_cstr.to_str().map_err(|e| unsafe {
        *err_msg = CString::new(format!(
            "Error on converting C char to rust str: {e}"
        ))
        .unwrap()
        .into_raw();
        *err_kind = CString::new(format!("{}", ErrorKind::InvalidArgument))
            .unwrap()
            .into_raw();
        NMSTATE_FAIL
    })?;
    NetworkState::new_from_yaml(net_state_str).map_err(|e| unsafe {
        *err_msg = CString::new(format!(
            "Error on converting string to rust NetworkState: {e}"
        ))
        .unwrap()
        .into_raw();
        *err_kind = CString::new(format!("{}", e.kind())).unwrap().into_raw();
        NMSTATE_FAIL
    })
}

pub(crate) fn is_state_in_json(state: *const c_char) -> bool {
    let net_state_cstr = unsafe { CStr::from_ptr(state) };
    if let Ok(net_state_str) = net_state_cstr.to_str() {
        serde_json::from_str::<serde_json::Value>(net_state_str).is_ok()
    } else {
        false
    }
}
