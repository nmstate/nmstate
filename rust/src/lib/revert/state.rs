// SPDX-License-Identifier: Apache-2.0

use serde_json::{Map, Value};

pub(crate) fn gen_revert_state(
    desired: &Value,
    current: &Value,
    revert: &mut Value,
) {
    match desired {
        Value::Object(des_obj) => {
            let cur_obj = if let Some(c) = current.as_object() {
                c
            } else {
                log::debug!("Current is not Value::Object but {current:?}");
                return;
            };
            let rev_obj = if let Some(r) = revert.as_object_mut() {
                r
            } else {
                log::debug!("Current is not Value::Object but {current:?}");
                return;
            };
            for (key, des_value) in des_obj.iter() {
                let cur_value = if let Some(c) = cur_obj.get(key) {
                    c
                } else {
                    log::debug!(
                        "Current does not have key {key}, \
                        desired value {des_value} full current: \
                        {current:?}"
                    );
                    continue;
                };
                if des_value.is_object() {
                    let mut rev_sub_value = Value::Object(Map::new());
                    gen_revert_state(des_value, cur_value, &mut rev_sub_value);
                    rev_obj.insert(key.clone(), rev_sub_value);
                } else {
                    rev_obj.insert(key.clone(), cur_value.clone());
                }
            }
        }
        _ => {
            log::error!(
                "BUG: gen_revert_state() got desired non-object value: {:?}",
                desired
            );
        }
    }
}
