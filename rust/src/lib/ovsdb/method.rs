// SPDX-License-Identifier: Apache-2.0

// Hold 'RPC Methods' defined in RFC-7047

use serde_json::{Map, Value};

use super::OvsDbOperation;

/// OVS DB Echo Method
/// used by both clients and servers to verify the liveness of a database
/// connection
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct OvsDbMethodEcho;

impl OvsDbMethodEcho {
    pub(crate) fn to_value(transaction_id: u64) -> Value {
        let mut ret = Map::new();
        ret.insert("method".to_string(), Value::String("echo".to_string()));
        ret.insert(
            "params".to_string(),
            Value::Array(vec![Value::String("hello_from_nmstate".to_string())]),
        );
        ret.insert("id".to_string(), Value::Number(transaction_id.into()));
        Value::Object(ret)
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct OvsDbMethodTransact {
    pub(crate) db_name: String,
    pub(crate) operations: Vec<OvsDbOperation>,
}

impl OvsDbMethodTransact {
    pub(crate) fn to_value(&self, transaction_id: u64) -> Value {
        let mut ret = Map::new();
        ret.insert("method".to_string(), Value::String("transact".to_string()));
        let mut params = vec![Value::String(self.db_name.clone())];
        for operation in self.operations.as_slice() {
            params.push(operation.to_value());
        }
        ret.insert("params".to_string(), Value::Array(params));
        ret.insert("id".to_string(), Value::Number(transaction_id.into()));
        Value::Object(ret)
    }
}
