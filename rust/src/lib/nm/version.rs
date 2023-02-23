// SPDX-License-Identifier: Apache-2.0

use crate::NmstateError;

// This helper function will help us to avoid introducing new dependencies to
// the project.
#[cfg(feature = "query_apply")]
pub(crate) fn nm_supports_accept_all_mac_addresses_mode(
) -> Result<bool, NmstateError> {
    let version = {
        let nm_api = crate::nm::nm_dbus::NmApi::new()
            .map_err(crate::nm::error::nm_error_to_nmstate)?;
        nm_api
            .version()
            .map_err(crate::nm::error::nm_error_to_nmstate)?
    };
    let version_split = version.split('.');
    let supported_version = Vec::<u32>::from([1, 32]);
    let mut supported_elem = supported_version.iter();

    for v_elem in version_split {
        if v_elem.chars().all(char::is_numeric) {
            if let Some(supported_v) = supported_elem.next() {
                if v_elem.parse::<u32>().unwrap_or_default() < *supported_v {
                    return Ok(false);
                }
            } else {
                return Ok(true);
            }
        }
    }
    Ok(true)
}

#[cfg(not(feature = "query_apply"))]
pub(crate) fn nm_supports_accept_all_mac_addresses_mode(
) -> Result<bool, NmstateError> {
    Ok(true)
}

#[cfg(feature = "query_apply")]
pub(crate) fn nm_supports_replace_local_rule() -> Result<bool, NmstateError> {
    let version = {
        let nm_api = crate::nm::nm_dbus::NmApi::new()
            .map_err(crate::nm::error::nm_error_to_nmstate)?;
        nm_api
            .version()
            .map_err(crate::nm::error::nm_error_to_nmstate)?
    };
    let version_split = version.split('.');
    let supported_version = Vec::<u32>::from([1, 42]);
    let mut supported_elem = supported_version.iter();

    for v_elem in version_split {
        if v_elem.chars().all(char::is_numeric) {
            if let Some(supported_v) = supported_elem.next() {
                if v_elem.parse::<u32>().unwrap_or_default() < *supported_v {
                    return Ok(false);
                }
            } else {
                return Ok(true);
            }
        }
    }
    Ok(true)
}

#[cfg(not(feature = "query_apply"))]
pub(crate) fn nm_supports_replace_local_rule() -> Result<bool, NmstateError> {
    Ok(true)
}
