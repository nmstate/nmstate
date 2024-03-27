// SPDX-License-Identifier: Apache-2.0

use serde_json::Value;

#[cfg(feature = "query_apply")]
fn _get_json_value_difference<'a, 'b>(
    reference: String,
    desire: &'a Value,
    current: &'b Value,
) -> Option<(String, &'a Value, &'b Value)> {
    match (desire, current) {
        (Value::Bool(des), Value::Bool(cur)) => {
            if des != cur {
                Some((reference, desire, current))
            } else {
                None
            }
        }
        (Value::Number(des), Value::Number(cur)) => {
            if des != cur {
                Some((reference, desire, current))
            } else {
                None
            }
        }
        (Value::String(des), Value::String(cur)) => {
            if des != cur {
                if des == crate::NetworkState::PASSWORD_HID_BY_NMSTATE {
                    None
                } else {
                    Some((reference, desire, current))
                }
            } else {
                None
            }
        }
        (Value::Array(des), Value::Array(cur)) => {
            if des.len() != cur.len() {
                Some((reference, desire, current))
            } else {
                for (index, des_element) in des.iter().enumerate() {
                    // The [] is safe as we already checked the length
                    let cur_element = &cur[index];
                    if let Some(difference) = get_json_value_difference(
                        format!("{}[{index}]", &reference),
                        des_element,
                        cur_element,
                    ) {
                        return Some(difference);
                    }
                }
                None
            }
        }
        (Value::Object(des), Value::Object(cur)) => {
            for (key, des_value) in des.iter() {
                let reference = format!("{reference}.{key}");
                if let Some(cur_value) = cur.get(key) {
                    if let Some(difference) = get_json_value_difference(
                        reference.clone(),
                        des_value,
                        cur_value,
                    ) {
                        return Some(difference);
                    }
                } else if des_value != &Value::Null {
                    return Some((reference, des_value, &Value::Null));
                }
            }
            None
        }
        (Value::Null, _) => None,
        (_, _) => Some((reference, desire, current)),
    }
}

#[cfg(feature = "query_apply")]
pub(crate) fn get_json_value_difference<'a, 'b>(
    reference: String,
    desire: &'a Value,
    current: &'b Value,
) -> Option<(String, &'a Value, &'b Value)> {
    if let Some((reference, desire, current)) =
        _get_json_value_difference(reference, desire, current)
    {
        if should_ignore(reference.as_str(), desire, current) {
            None
        } else {
            Some((reference, desire, current))
        }
    } else {
        None
    }
}

#[cfg(feature = "query_apply")]
fn should_ignore(reference: &str, desire: &Value, current: &Value) -> bool {
    if reference.contains("interface.link-aggregation.options") {
        // Per oVirt request, bond option difference should not
        // fail verification.
        log::warn!(
            "Bond option miss-match: {} desire '{}', current '{}'",
            reference,
            desire,
            current
        );
        true
    } else {
        false
    }
}

#[cfg(feature = "query_apply")]
pub(crate) fn gen_diff_json_value(
    desired: &Value,
    current: &Value,
) -> Option<Value> {
    match desired {
        Value::Object(des_obj) => {
            if let Some(cur_obj) = current.as_object() {
                let mut diff_map = serde_json::Map::new();
                for (des_key, des_value) in des_obj.iter() {
                    if let Some(cur_value) = cur_obj.get(des_key) {
                        if let Some(ret) =
                            gen_diff_json_value(des_value, cur_value)
                        {
                            diff_map.insert(des_key.clone(), ret);
                        }
                    } else {
                        diff_map.insert(des_key.clone(), des_value.clone());
                    }
                }
                if diff_map.is_empty() {
                    None
                } else {
                    Some(Value::Object(diff_map))
                }
            } else {
                Some(desired.clone())
            }
        }
        _ => {
            if desired != current {
                Some(desired.clone())
            } else {
                None
            }
        }
    }
}

// Whatever not defined in desired but defined in current will be copied
pub(crate) fn merge_json_value(desired: &mut Value, current: &Value) {
    if let (Some(desired), Some(current)) =
        (desired.as_object_mut(), current.as_object())
    {
        for (cur_key, cur_value) in current.iter() {
            if let Some(des_value) = desired.get_mut(cur_key) {
                merge_json_value(des_value, cur_value);
            } else {
                desired.insert(cur_key.clone(), cur_value.clone());
            }
        }
    }
}
