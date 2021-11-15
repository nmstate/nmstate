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

use crate::error::{ErrorKind, NmError};
use std::convert::TryFrom;

const DBUS_SIGNATURE_STRING: &str = "s";
const DBUS_SIGNATURE_BOOL: &str = "b";
const DBUS_SIGNATURE_I32: &str = "i";
const DBUS_SIGNATURE_U32: &str = "u";
const DBUS_SIGNATURE_ARRAY: &str = "a";
const DBUS_SIGNATURE_BYTES_ARRAY: &str = "ay";

pub(crate) fn own_value_to_string(
    value: zvariant::OwnedValue,
) -> Result<String, NmError> {
    check_value_is_string(&value)?;
    let err_msg = format!("Failed to convert {:?} to string", &value);
    <String>::try_from(value).map_err(|e| {
        NmError::new(ErrorKind::Bug, format!("{}: {}", err_msg, e))
    })
}

// TODO: Use macro instead
pub(crate) fn own_value_to_bool(
    value: zvariant::OwnedValue,
) -> Result<bool, NmError> {
    check_value_is_bool(&value)?;
    let err_msg = format!("Failed to convert {:?} to bool", &value);
    match <bool>::try_from(value) {
        Ok(s) => Ok(s),
        Err(e) => {
            Err(NmError::new(ErrorKind::Bug, format!("{}: {}", err_msg, e)))
        }
    }
}

// TODO: Use macro instead
pub(crate) fn own_value_to_i32(
    value: zvariant::OwnedValue,
) -> Result<i32, NmError> {
    check_value_is_i32(&value)?;
    let err_msg = format!("Failed to convert {:?} to i32", &value);
    match <i32>::try_from(value) {
        Ok(s) => Ok(s),
        Err(e) => {
            Err(NmError::new(ErrorKind::Bug, format!("{}: {}", err_msg, e)))
        }
    }
}

// TODO: Use macro instead
pub(crate) fn own_value_to_u32(
    value: zvariant::OwnedValue,
) -> Result<u32, NmError> {
    check_value_is_u32(&value)?;
    let err_msg = format!("Failed to convert {:?} to u32", &value);
    match <u32>::try_from(value) {
        Ok(s) => Ok(s),
        Err(e) => {
            Err(NmError::new(ErrorKind::Bug, format!("{}: {}", err_msg, e)))
        }
    }
}

// TODO: Use macro instead
pub(crate) fn own_value_to_array(
    value: zvariant::OwnedValue,
) -> Result<Vec<zvariant::OwnedValue>, NmError> {
    check_value_is_array(&value)?;
    let err_msg = format!("Failed to convert {:?} to array", &value);
    <Vec<zvariant::OwnedValue>>::try_from(value).map_err(|e| {
        NmError::new(ErrorKind::Bug, format!("{}: {}", err_msg, e))
    })
}

// TODO: Use macro instead
pub(crate) fn own_value_to_bytes_array(
    value: zvariant::OwnedValue,
) -> Result<Vec<u8>, NmError> {
    check_value_is_bytes_array(&value)?;
    let err_msg = format!("Failed to convert {:?} to bytes array", &value);
    match <zvariant::Array>::try_from(value) {
        Ok(s) => {
            let mut bytes_array: Vec<u8> = Vec::new();
            for item in s.iter() {
                if let zvariant::Value::U8(i) = item {
                    bytes_array.push(*i);
                }
            }
            Ok(bytes_array)
        }
        Err(e) => {
            Err(NmError::new(ErrorKind::Bug, format!("{}: {}", err_msg, e)))
        }
    }
}

fn check_value_is_string(value: &zvariant::OwnedValue) -> Result<(), NmError> {
    if value.value_signature().as_str() != DBUS_SIGNATURE_STRING {
        Err(NmError::new(
            ErrorKind::Bug,
            format!("OwnedValue {:?} is not string", &value),
        ))
    } else {
        Ok(())
    }
}

fn check_value_is_bool(value: &zvariant::OwnedValue) -> Result<(), NmError> {
    if value.value_signature().as_str() != DBUS_SIGNATURE_BOOL {
        Err(NmError::new(
            ErrorKind::Bug,
            format!("OwnedValue {:?} is not bool", &value),
        ))
    } else {
        Ok(())
    }
}

fn check_value_is_i32(value: &zvariant::OwnedValue) -> Result<(), NmError> {
    if value.value_signature().as_str() != DBUS_SIGNATURE_I32 {
        Err(NmError::new(
            ErrorKind::Bug,
            format!("OwnedValue {:?} is not i32", &value),
        ))
    } else {
        Ok(())
    }
}

fn check_value_is_u32(value: &zvariant::OwnedValue) -> Result<(), NmError> {
    if value.value_signature().as_str() != DBUS_SIGNATURE_U32 {
        Err(NmError::new(
            ErrorKind::Bug,
            format!("OwnedValue {:?} is not u32", &value),
        ))
    } else {
        Ok(())
    }
}

fn check_value_is_array(value: &zvariant::OwnedValue) -> Result<(), NmError> {
    if !value
        .value_signature()
        .as_str()
        .starts_with(DBUS_SIGNATURE_ARRAY)
    {
        Err(NmError::new(
            ErrorKind::Bug,
            format!("OwnedValue {:?} is not array", &value),
        ))
    } else {
        Ok(())
    }
}

fn check_value_is_bytes_array(
    value: &zvariant::OwnedValue,
) -> Result<(), NmError> {
    if !value
        .value_signature()
        .as_str()
        .starts_with(DBUS_SIGNATURE_BYTES_ARRAY)
    {
        Err(NmError::new(
            ErrorKind::Bug,
            format!("OwnedValue {:?} is not bytes array", &value),
        ))
    } else {
        Ok(())
    }
}
