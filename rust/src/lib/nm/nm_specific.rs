use std::collections::HashMap;

use crate::nm::nm_dbus::NmConnection;

const BACKEND_SPECIFIC_KEY: &str = "networkmanager";

const NM_ID_KEY: &str = "connection.id";
const NM_UUID_KEY: &str = "connection.uuid";
const NM_IPV4_MAY_FAIL_KEY: &str = "ipv4.may-fail";
const NM_IPV6_MAY_FAIL_KEY: &str = "ipv6.may-fail";

// We are not allowing arbitrary settings be case we are supposed to set the
// data type before sending to NM via dbus
pub(crate) fn apply_backend_specific_config(
    config: &HashMap<String, serde_json::Value>,
    nm_conn: &mut NmConnection,
) {
    if let Some(config) =
        config.get(BACKEND_SPECIFIC_KEY).and_then(|v| v.as_object())
    {
        if let Some(v) = config.get(NM_ID_KEY).and_then(|v| v.as_str()) {
            if let Some(nm_set) = nm_conn.connection.as_mut() {
                nm_set.id = Some(v.to_string());
            }
        }
        if let Some(v) = config.get(NM_UUID_KEY).and_then(|v| v.as_str()) {
            if let Some(nm_set) = nm_conn.connection.as_mut() {
                nm_set.uuid = Some(v.to_string());
            }
        }
        if let Some(v) = value_get_bool(config, NM_IPV4_MAY_FAIL_KEY) {
            if let Some(nm_set) = nm_conn.ipv4.as_mut() {
                nm_set.may_fail = Some(v);
            }
        }
        if let Some(v) = value_get_bool(config, NM_IPV6_MAY_FAIL_KEY) {
            if let Some(nm_set) = nm_conn.ipv6.as_mut() {
                nm_set.may_fail = Some(v);
            }
        }
    }
}

pub(crate) fn get_backend_specific_config(
    nm_conn: &NmConnection,
) -> HashMap<String, serde_json::Value> {
    let mut nm_specific = serde_json::Map::new();
    if let Some(v) = nm_conn.id() {
        nm_specific.insert(
            NM_ID_KEY.to_string(),
            serde_json::Value::String(v.to_string()),
        );
    }
    if let Some(v) = nm_conn.uuid() {
        nm_specific.insert(
            NM_UUID_KEY.to_string(),
            serde_json::Value::String(v.to_string()),
        );
    }
    if let Some(nm_set) = nm_conn.ipv4.as_ref() {
        nm_specific.insert(
            NM_IPV4_MAY_FAIL_KEY.to_string(),
            serde_json::Value::Bool(nm_set.may_fail.unwrap_or(true)),
        );
    }
    if let Some(nm_set) = nm_conn.ipv6.as_ref() {
        nm_specific.insert(
            NM_IPV6_MAY_FAIL_KEY.to_string(),
            serde_json::Value::Bool(nm_set.may_fail.unwrap_or(true)),
        );
    }

    let mut ret = HashMap::new();
    ret.insert(
        BACKEND_SPECIFIC_KEY.to_string(),
        serde_json::Value::Object(nm_specific),
    );
    ret
}

fn value_get_bool(
    value: &serde_json::Map<String, serde_json::Value>,
    key: &str,
) -> Option<bool> {
    if let Some(v) = value.get(key) {
        if let Some(v) = v.as_str() {
            match v {
                "true" | "True" | "yes" | "y" | "1" => return Some(true),
                "false" | "False" | "no" | "n" | "0" => return Some(false),
                _ => (),
            }
        }
        if let Some(v) = v.as_bool() {
            return Some(v);
        }
        if let Some(v) = v.as_u64() {
            match v {
                1 => Some(true),
                0 => Some(false),
                _ => None,
            }
        } else {
            None
        }
    } else {
        None
    }
}
