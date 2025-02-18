// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde_json::{Map, Value};

use super::{
    db::parse_str_map, OvsDbConnection, OvsDbMethodTransact, OvsDbMutate,
    OvsDbMutation, OvsDbOperation, OvsDbSelect, OvsDbUpdate, OVS_DB_NAME,
};
use crate::{ErrorKind, MergedNetworkState, NmstateError, OvsDbGlobalConfig};

const GLOBAL_CONFIG_TABLE: &str = "Open_vSwitch";

impl From<&Map<std::string::String, Value>> for OvsDbGlobalConfig {
    fn from(m: &Map<std::string::String, Value>) -> Self {
        let mut ret = Self::default();
        if let (Some(Value::Array(ids)), Some(Value::Array(other_cfg))) =
            (m.get("external_ids"), m.get("other_config"))
        {
            ret.external_ids = Some(convert_map(parse_str_map(ids)));
            ret.other_config = Some(convert_map(parse_str_map(other_cfg)));
        }
        ret
    }
}

// Convert HashMap<String, String> to HashMap<String, Option<String>>
fn convert_map(
    mut m: HashMap<String, String>,
) -> HashMap<String, Option<String>> {
    let mut ret = HashMap::new();
    for (k, v) in m.drain() {
        ret.insert(k, Some(v));
    }
    ret
}

impl OvsDbConnection {
    pub(crate) fn get_global_conf(
        &mut self,
    ) -> Result<OvsDbGlobalConfig, NmstateError> {
        let reply = self.transact(&OvsDbMethodTransact {
            db_name: OVS_DB_NAME.to_string(),
            operations: vec![OvsDbOperation::Select(OvsDbSelect {
                table: GLOBAL_CONFIG_TABLE.to_string(),
                conditions: vec![],
                columns: Some(vec!["external_ids", "other_config"]),
            })],
        })?;

        if let Some(global_conf) = reply
            .as_array()
            .and_then(|reply| reply.first())
            .and_then(|v| v.as_object())
            .and_then(|v| v.get("rows"))
            .and_then(|v| v.as_array())
            .and_then(|v| v.first())
            .and_then(|v| v.as_object())
        {
            Ok(global_conf.into())
        } else {
            let e = NmstateError::new(
                ErrorKind::PluginFailure,
                format!(
                    "Invalid reply from OVSDB for querying \
                    {GLOBAL_CONFIG_TABLE} table: {reply:?}"
                ),
            );
            log::error!("{}", e);
            Err(e)
        }
    }
}

fn append_purge_action(operations: &mut Vec<OvsDbOperation>, column: &str) {
    log::info!("Purging OVS table {GLOBAL_CONFIG_TABLE} table column {column}");
    let mut row = HashMap::new();
    row.insert(
        column.to_string(),
        Value::Array(vec![
            Value::String("map".to_string()),
            Value::Array(Vec::new()),
        ]),
    );
    operations.push(OvsDbOperation::Update(OvsDbUpdate {
        table: GLOBAL_CONFIG_TABLE.to_string(),
        conditions: Vec::new(),
        row,
    }))
}

// Use `delete` mutator for Value set to None, otherwise use `insert`.
fn append_mutations(
    mutations: &mut Vec<OvsDbMutation>,
    column: &str,
    data: &HashMap<String, Option<String>>,
) {
    // All key should be deleted first because `insert` does not override
    // existing values.
    let delete_keys: Vec<Value> = data
        .keys()
        .map(|k| {
            log::debug!("Removing old value of key {} from {}", k, column);
            Value::String(k.to_string())
        })
        .collect();
    if !delete_keys.is_empty() {
        mutations.push(OvsDbMutation {
            column: column.to_string(),
            mutator: "delete".to_string(),
            value: Value::Array(vec![
                Value::String("set".to_string()),
                Value::Array(delete_keys),
            ]),
        })
    }
    let insert_values: Vec<Value> = data
        .iter()
        .filter_map(|(k, v)| {
            v.as_ref().map(|v| {
                log::info!("Inserting key {} value {} into {}", k, v, column);
                Value::Array(vec![
                    Value::String(k.to_string()),
                    Value::String(v.to_string()),
                ])
            })
        })
        .collect();
    if !insert_values.is_empty() {
        mutations.push(OvsDbMutation {
            column: column.to_string(),
            mutator: "insert".to_string(),
            value: Value::Array(vec![
                Value::String("map".to_string()),
                Value::Array(insert_values),
            ]),
        })
    }
}

pub(crate) fn ovsdb_apply_global_conf(
    merged_state: &MergedNetworkState,
) -> Result<(), NmstateError> {
    if !merged_state.ovsdb.is_changed() && !merged_state.ovn.is_changed() {
        log::debug!("No OVSDB changes");
        return Ok(());
    }

    let mut cli = OvsDbConnection::new()?;
    let mut operations = Vec::new();
    let mut is_external_ids_purged = false;

    if let Some(desired_ovsdb) = merged_state.ovsdb.desired.as_ref() {
        if desired_ovsdb.is_purge() {
            is_external_ids_purged = true;
            append_purge_action(&mut operations, "external_ids");
            append_purge_action(&mut operations, "other_config");
        } else {
            let mut mutations = Vec::new();
            if let Some(external_ids) = desired_ovsdb.external_ids.as_ref() {
                // Whether user is purging all external_ids
                if external_ids.is_empty() {
                    is_external_ids_purged = true;
                    append_purge_action(&mut operations, "external_ids");
                } else {
                    append_mutations(
                        &mut mutations,
                        "external_ids",
                        external_ids,
                    );
                }
            }
            if let Some(other_config) = desired_ovsdb.other_config.as_ref() {
                if other_config.is_empty() {
                    append_purge_action(&mut operations, "other_config");
                } else {
                    append_mutations(
                        &mut mutations,
                        "other_config",
                        other_config,
                    );
                }
            }
            if !mutations.is_empty() {
                operations.push(OvsDbOperation::Mutate(OvsDbMutate {
                    table: GLOBAL_CONFIG_TABLE.to_string(),
                    conditions: Vec::new(),
                    mutations,
                }));
            }
        }
    }

    let ovn_map_value = merged_state.ovn.to_ovsdb_external_id_value();

    // When OVSDB is purging, we should preserve current OVN mapping
    // regardless it is changed or not.
    if merged_state.ovn.is_changed()
        || (is_external_ids_purged && ovn_map_value.is_some())
    {
        let mut ovn_external_ids = HashMap::new();
        ovn_external_ids
            .insert("ovn-bridge-mappings".to_string(), ovn_map_value);

        let mut mutations = Vec::new();
        // Remove then insert again
        mutations.push(OvsDbMutation {
            column: "external_ids".to_string(),
            mutator: "delete".to_string(),
            value: Value::Array(vec![
                Value::String("set".to_string()),
                Value::Array(vec![Value::String(
                    "ovn-bridge-mappings".to_string(),
                )]),
            ]),
        });
        append_mutations(&mut mutations, "external_ids", &ovn_external_ids);

        operations.push(OvsDbOperation::Mutate(OvsDbMutate {
            table: GLOBAL_CONFIG_TABLE.to_string(),
            conditions: Vec::new(),
            mutations,
        }));
    }

    if !operations.is_empty() {
        let transact = OvsDbMethodTransact {
            db_name: OVS_DB_NAME.to_string(),
            operations,
        };
        cli.transact(&transact)?;
    }
    Ok(())
}
