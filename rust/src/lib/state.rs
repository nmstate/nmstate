use serde_json::Value;

pub(crate) fn get_json_value_difference(
    reference: String,
    desire: &Value,
    current: &Value,
) -> Option<Value> {
    match (desire, current) {
        (Value::Bool(des), Value::Bool(cur)) => {
            if des != cur {
                Some(Value::String(format!(
                    "{}: desire bool: {}, current: {}",
                    &reference, des, cur
                )))
            } else {
                None
            }
        }
        (Value::Number(des), Value::Number(cur)) => {
            if des != cur {
                Some(Value::String(format!(
                    "{}: desire number: {}, current: {}",
                    &reference, des, cur
                )))
            } else {
                None
            }
        }
        (Value::String(des), Value::String(cur)) => {
            if des != cur {
                Some(Value::String(format!(
                    "{}: desire string: {}, current: {}",
                    &reference, des, cur
                )))
            } else {
                None
            }
        }
        (Value::Array(des), Value::Array(cur)) => {
            if des.len() != cur.len() {
                Some(Value::String(format!(
                    "{} different array length {} vs {}: \
                    desire {}, current: {}",
                    &reference,
                    des.len(),
                    cur.len(),
                    desire,
                    current
                )))
            } else {
                for (index, des_element) in des.iter().enumerate() {
                    // The [] is safe as we already checked the length
                    let cur_element = &cur[index];
                    if let Some(difference) = get_json_value_difference(
                        format!("{}[{}]", &reference, index),
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
                let reference = format!("{}.{}", reference, key);
                if let Some(cur_value) = cur.get(key) {
                    if let Some(difference) = get_json_value_difference(
                        reference.clone(),
                        des_value,
                        cur_value,
                    ) {
                        return Some(difference);
                    }
                } else {
                    return Some(Value::String(format!(
                        "{}: desire: {}, current: None",
                        &reference, des_value
                    )));
                }
            }
            None
        }
        (Value::Null, _) => None,
        (_, _) => Some(Value::String(format!(
            "{}: type miss match, desire: {} current: {}",
            &reference, desire, current
        ))),
    }
}
