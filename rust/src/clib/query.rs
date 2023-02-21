// SPDX-License-Identifier: Apache-2.0

use std::ffi::CString;
use std::time::SystemTime;

use libc::{c_char, c_int};

use crate::{init_logger, NMSTATE_FAIL, NMSTATE_PASS};

pub(crate) const NMSTATE_FLAG_KERNEL_ONLY: u32 = 1 << 1;
pub(crate) const NMSTATE_FLAG_NO_VERIFY: u32 = 1 << 2;
pub(crate) const NMSTATE_FLAG_INCLUDE_STATUS_DATA: u32 = 1 << 3;
pub(crate) const NMSTATE_FLAG_INCLUDE_SECRETS: u32 = 1 << 4;
pub(crate) const NMSTATE_FLAG_NO_COMMIT: u32 = 1 << 5;
pub(crate) const NMSTATE_FLAG_MEMORY_ONLY: u32 = 1 << 6;
pub(crate) const NMSTATE_FLAG_RUNNING_CONFIG_ONLY: u32 = 1 << 7;
pub(crate) const NMSTATE_FLAG_YAML_OUTPUT: u32 = 1 << 8;

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

    if (flags & NMSTATE_FLAG_RUNNING_CONFIG_ONLY) > 0 {
        net_state.set_running_config_only(true);
    }

    let result = net_state.retrieve();
    unsafe {
        *log = CString::new(logger.drain(now)).unwrap().into_raw();
    }

    match result {
        Ok(s) => {
            let serialize = if (flags & NMSTATE_FLAG_YAML_OUTPUT) > 0 {
                serde_yaml::to_string(&s).map_err(|e| {
                    nmstate::NmstateError::new(
                        nmstate::ErrorKind::Bug,
                        format!("Failed to convert state {s:?} to YAML: {e}"),
                    )
                })
            } else {
                serde_json::to_string(&s).map_err(|e| {
                    nmstate::NmstateError::new(
                        nmstate::ErrorKind::Bug,
                        format!("Failed to convert state {s:?} to JSON: {e}"),
                    )
                })
            };

            match serialize {
                Ok(state_str) => unsafe {
                    *state = CString::new(state_str).unwrap().into_raw();
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
