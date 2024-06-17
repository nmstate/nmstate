// SPDX-License-Identifier: Apache-2.0

use serde::Serializer;

pub(crate) fn is_option_string_empty(data: &Option<String>) -> bool {
    if let Some(s) = data {
        s.is_empty()
    } else {
        true
    }
}

pub(crate) fn option_u32_as_hex<S>(
    data: &Option<u32>,
    serializer: S,
) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    if let Some(v) = data {
        serializer.serialize_str(format!("{v:#x?}").as_str())
    } else {
        serializer.serialize_none()
    }
}
