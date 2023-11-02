// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, NmstateError};

use super::capture::PROPERTY_SPLITTER;

pub(crate) fn get_value_from_json(
    prop_path: &[String],
    data: &serde_json::Map<String, serde_json::Value>,
    line: &str,
    pos: usize,
) -> Result<serde_json::Value, NmstateError> {
    match prop_path.len().cmp(&1) {
        std::cmp::Ordering::Less => Err(NmstateError::new(
            ErrorKind::Bug,
            "Got zero length prop_path".to_string(),
        )),
        // Reached the final
        std::cmp::Ordering::Equal => match data.get(&prop_path[0]) {
            Some(v) => Ok(v.clone()),
            None => Err(NmstateError::new_policy_error(
                format!(
                    "Failed to find property {}, exists properties are {}",
                    prop_path[0],
                    data.keys()
                        .map(|k| k.as_str())
                        .collect::<Vec<&str>>()
                        .join(",")
                ),
                line,
                pos,
            )),
        },
        // Still have leaf
        std::cmp::Ordering::Greater => match data.get(&prop_path[0]) {
            Some(v) => {
                if let Some(index) = prop_path
                    .get(1)
                    .and_then(|index_str| index_str.parse::<usize>().ok())
                {
                    get_leaf_array_value(
                        prop_path[0].as_str(),
                        &prop_path[2..],
                        v,
                        index,
                        line,
                        pos + format!("{}.{}.", prop_path[0], prop_path[1])
                            .chars()
                            .count(),
                    )
                } else if let Some(leaf) = v.as_object() {
                    get_value_from_json(
                        &prop_path[1..],
                        leaf,
                        line,
                        pos + prop_path[0].to_string().chars().count(),
                    )
                } else {
                    Err(NmstateError::new_policy_error(
                        format!(
                            "The {} leaf data is not a object",
                            prop_path[0]
                        ),
                        line,
                        pos,
                    ))
                }
            }
            None => Err(NmstateError::new_policy_error(
                format!(
                    "Failed to find leaf {} data, allowed keys are {}",
                    prop_path[0],
                    data.keys()
                        .map(|s| s.as_str())
                        .collect::<Vec<&str>>()
                        .join(",")
                ),
                line,
                pos,
            )),
        },
    }
}

pub(crate) fn value_to_string(v: &serde_json::Value) -> String {
    match v.as_str() {
        Some(v) => v.to_string(),
        None => v.to_string(),
    }
}

pub(crate) fn search_item<T>(
    item_name: &str,
    prop_path: &[String],
    value: &str,
    items: &[T],
    line: &str,
    pos: usize,
) -> Result<Vec<T>, NmstateError>
where
    T: Clone + serde::Serialize,
{
    let mut ret = Vec::new();
    for item in items {
        let item_value = match serde_json::to_value(item) {
            Ok(v) => v,
            Err(_) => continue,
        };
        let item_value = match item_value.as_object() {
            Some(v) => v,
            None => continue,
        };

        let cur_value =
            match get_value_from_json(prop_path, item_value, line, pos) {
                Ok(v) => v,
                Err(_) => continue,
            };
        if value_to_string(&cur_value).as_str() == value {
            ret.push(item.clone());
        }
    }
    if ret.is_empty() {
        Err(NmstateError::new_policy_error(
            format!(
                "{} with '{}={}' not found",
                item_name,
                prop_path.join(PROPERTY_SPLITTER),
                value
            ),
            line,
            pos,
        ))
    } else {
        Ok(ret)
    }
}

fn get_leaf_array_value(
    item_name: &str,
    prop_path: &[String],
    value: &serde_json::Value,
    index: usize,
    line: &str,
    pos: usize,
) -> Result<serde_json::Value, NmstateError> {
    let leaf = match value.as_array().and_then(|items| items.get(index)) {
        Some(l) => l,
        None => {
            return Err(NmstateError::new_policy_error(
                format!("Failed to find index {index} from {item_name}"),
                line,
                pos,
            ));
        }
    };
    if prop_path.is_empty() {
        Ok(leaf.clone())
    } else if let Some(leaf) = leaf.as_object() {
        get_value_from_json(
            prop_path,
            leaf,
            line,
            pos + format!("{index}.").chars().count(),
        )
    } else {
        Err(NmstateError::new_policy_error(
            format!("The {item_name} index {index} leaf data is not a object"),
            line,
            pos,
        ))
    }
}

pub(crate) fn update_json_value(
    item_name: &str,
    prop_path: &[String],
    value: Option<&str>,
    data: &mut serde_json::Map<String, serde_json::Value>,
) -> Result<(), NmstateError> {
    match prop_path.len().cmp(&1) {
        std::cmp::Ordering::Less => Err(NmstateError::new(
            ErrorKind::Bug,
            "Got zero length prop_path".to_string(),
        )),
        // Reached the final
        std::cmp::Ordering::Equal => {
            if let Some(old_value) = data.get(&prop_path[0]) {
                log::debug!(
                    "Changing {} property of {} from {} to {}",
                    &prop_path[0],
                    item_name,
                    old_value,
                    value.unwrap_or("null")
                );
                data.insert(
                    prop_path[0].to_string(),
                    if let Some(v) = value {
                        serde_json::Value::String(v.to_string())
                    } else {
                        serde_json::Value::Null
                    },
                );
                Ok(())
            } else {
                log::debug!(
                    "Inserting new property {}:{} to {}",
                    &prop_path[0],
                    value.unwrap_or("null"),
                    item_name
                );
                data.insert(
                    prop_path[0].to_string(),
                    if let Some(v) = value {
                        serde_json::Value::String(v.to_string())
                    } else {
                        serde_json::Value::Null
                    },
                );
                Ok(())
            }
        }
        // Still have left
        std::cmp::Ordering::Greater => match data.get_mut(&prop_path[0]) {
            Some(v) => {
                if let Some(leaf) = v.as_object_mut() {
                    update_json_value(item_name, &prop_path[1..], value, leaf)
                } else {
                    Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "The {} leaf data {:?} is not a object",
                            prop_path[0], v
                        ),
                    ))
                }
            }
            None => {
                // We should create new Map and move on
                data.insert(
                    prop_path[0].to_string(),
                    serde_json::Value::Object(serde_json::Map::new()),
                );
                if let Some(v) = data.get_mut(&prop_path[0]) {
                    if let Some(leaf) = v.as_object_mut() {
                        update_json_value(
                            item_name,
                            &prop_path[1..],
                            value,
                            leaf,
                        )
                    } else {
                        Err(NmstateError::new(
                            ErrorKind::Bug,
                            format!(
                                "Failed to get newly inserted map in {:?} \
                                for {}",
                                data, prop_path[0],
                            ),
                        ))
                    }
                } else {
                    Err(NmstateError::new(
                        ErrorKind::Bug,
                        format!(
                            "Failed to get newly inserted map in {:?} for {}",
                            data, prop_path[0],
                        ),
                    ))
                }
            }
        },
    }
}

pub(crate) fn update_items<T>(
    item_name: &str,
    prop_path: &[String],
    value: Option<&str>,
    items: &[T],
    line: &str,
    pos: usize,
) -> Result<Vec<T>, NmstateError>
where
    T: std::fmt::Debug
        + Clone
        + serde::Serialize
        + for<'de> serde::Deserialize<'de>,
{
    let mut ret = Vec::new();
    for item in items {
        let mut item_value = serde_json::to_value(item).map_err(|e| {
            NmstateError::new_policy_error(
                format!(
                    "Failed to convert {item:?} item into serde_json value: {e}"
                ),
                line,
                pos,
            )
        })?;
        if let Some(item_value) = item_value.as_object_mut() {
            update_json_value(item_name, prop_path, value, item_value)?;
            ret.push(
                serde_json::from_value(serde_json::Value::Object(
                    item_value.clone(),
                ))
                .map_err(|e| {
                    NmstateError::new(
                        ErrorKind::Bug,
                        format!(
                            "Failed to deserialize {item_value:?} into \
                            {item_name}: {e}"
                        ),
                    )
                })?,
            );
        }
    }
    Ok(ret)
}

pub(crate) fn value_retain_only(
    data: &mut serde_json::Value,
    prop_path: &[String],
) {
    if let Some(data) = data.as_object_mut() {
        if !prop_path.is_empty() {
            data.retain(|k, _| k == &prop_path[0]);
            if prop_path.len() >= 2 {
                if let Some(leaf) = data.get_mut(&prop_path[0]) {
                    value_retain_only(leaf, &prop_path[1..]);
                }
            }
        }
    }
}
