use serde_json::Value;

pub(crate) fn get_json_value_difference<'a, 'b>(
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
                Some((reference, desire, current))
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
