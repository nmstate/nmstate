// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde_json::Value;

use super::{
    json_rpc::OvsDbJsonRpc, OvsDbMethodEcho, OvsDbMethodTransact,
    OvsDbOperation, OvsDbSelect,
};
use crate::{ErrorKind, NmstateError};

pub(crate) const OVS_DB_NAME: &str = "Open_vSwitch";
const NM_RESERVED_EXTERNAL_ID: &str = "NM.connection.uuid";

pub(crate) const DEFAULT_OVS_DB_SOCKET_PATH: &str = "/run/openvswitch/db.sock";

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct OvsDbCondition {
    column: String,
    function: String,
    value: Value,
}

impl OvsDbCondition {
    pub(crate) fn to_value(&self) -> Value {
        Value::Array(vec![
            Value::String(self.column.to_string()),
            Value::String(self.function.to_string()),
            self.value.clone(),
        ])
    }
}

#[derive(Debug)]
pub(crate) struct OvsDbConnection {
    pub(crate) rpc: OvsDbJsonRpc,
    pub(crate) transaction_id: u64,
}

impl OvsDbConnection {
    pub(crate) fn get_transaction_id(&mut self) -> u64 {
        self.transaction_id += 1;
        self.transaction_id
    }

    // TODO: support environment variable OVS_DB_UNIX_SOCKET_PATH
    pub(crate) fn new() -> Result<Self, NmstateError> {
        Ok(Self {
            rpc: OvsDbJsonRpc::connect(DEFAULT_OVS_DB_SOCKET_PATH)?,
            transaction_id: 0,
        })
    }

    pub(crate) fn check_connection(&mut self) -> bool {
        let transaction_id = self.get_transaction_id();
        let value = OvsDbMethodEcho::to_value(transaction_id);
        if self.rpc.send(&value).is_ok() {
            self.rpc.recv(transaction_id).is_ok()
        } else {
            false
        }
    }

    pub(crate) fn transact(
        &mut self,
        transact: &OvsDbMethodTransact,
    ) -> Result<Value, NmstateError> {
        let transaction_id = self.get_transaction_id();
        let value = transact.to_value(transaction_id);
        self.rpc.send(&value)?;
        let reply = self.rpc.recv(transaction_id)?;
        check_transact_error(reply)
    }

    fn _get_ovs_entry(
        &mut self,
        table_name: &str,
        columns: Vec<&'static str>,
    ) -> Result<HashMap<String, OvsDbEntry>, NmstateError> {
        let reply = self.transact(&OvsDbMethodTransact {
            db_name: OVS_DB_NAME.to_string(),
            operations: vec![OvsDbOperation::Select(OvsDbSelect {
                table: table_name.to_string(),
                conditions: vec![],
                columns: Some(columns),
            })],
        })?;

        let mut ret: HashMap<String, OvsDbEntry> = HashMap::new();

        if let Some(entries) = reply
            .as_array()
            .and_then(|reply| reply.first())
            .and_then(|v| v.as_object())
            .and_then(|v| v.get("rows"))
            .and_then(|v| v.as_array())
        {
            for entry in entries {
                let ovsdb_entry: OvsDbEntry = entry.try_into()?;
                if !ovsdb_entry.uuid.is_empty() {
                    ret.insert(ovsdb_entry.uuid.to_string(), ovsdb_entry);
                }
            }
            Ok(ret)
        } else {
            let e = NmstateError::new(
                ErrorKind::PluginFailure,
                format!(
                    "Invalid reply from OVSDB for querying \
                    {table_name} table: {reply:?}"
                ),
            );
            log::error!("{}", e);
            Err(e)
        }
    }

    pub(crate) fn get_ovs_ifaces(
        &mut self,
    ) -> Result<HashMap<String, OvsDbEntry>, NmstateError> {
        self._get_ovs_entry(
            "Interface",
            vec![
                "external_ids",
                "name",
                "other_config",
                "_uuid",
                "type",
                "mtu",
                "options",
            ],
        )
    }

    pub(crate) fn get_ovs_ports(
        &mut self,
    ) -> Result<HashMap<String, OvsDbEntry>, NmstateError> {
        self._get_ovs_entry(
            "Port",
            vec![
                "external_ids",
                "name",
                "other_config",
                "_uuid",
                "interfaces",
                "vlan_mode",
                "tag",
                "trunks",
                "bond_mode",
                "bond_updelay",
                "bond_downdelay",
                "lacp",
            ],
        )
    }

    pub(crate) fn get_ovs_bridges(
        &mut self,
    ) -> Result<HashMap<String, OvsDbEntry>, NmstateError> {
        self._get_ovs_entry(
            "Bridge",
            vec![
                "external_ids",
                "name",
                "other_config",
                "_uuid",
                "ports",
                "stp_enable",
                "rstp_enable",
                "mcast_snooping_enable",
                "fail_mode",
                "datapath_type",
            ],
        )
    }
}

#[derive(Debug, Default)]
pub(crate) struct OvsDbEntry {
    pub(crate) uuid: String,
    pub(crate) name: String,
    pub(crate) external_ids: HashMap<String, String>,
    pub(crate) other_config: HashMap<String, String>,
    pub(crate) ports: Vec<String>,
    pub(crate) iface_type: String,
    pub(crate) options: HashMap<String, Value>,
}

impl TryFrom<&Value> for OvsDbEntry {
    type Error = NmstateError;
    fn try_from(v: &Value) -> Result<OvsDbEntry, Self::Error> {
        let e = NmstateError::new(
            ErrorKind::PluginFailure,
            format!("Failed to parse OVS Entry info from : {v:?}"),
        );
        let v = v.clone();
        let mut ret = OvsDbEntry::default();
        if let Value::Object(mut v) = v {
            if let Some(Value::String(n)) = v.remove("name") {
                ret.name = n;
                if let Some(Value::Array(uuid)) = v.remove("_uuid") {
                    if let Some(Value::String(uuid)) = uuid.get(1) {
                        ret.uuid = uuid.to_string();
                    }
                }
                if let Some(Value::String(iface_type)) = v.remove("type") {
                    ret.iface_type = iface_type;
                }
                if let Some(Value::Array(ids)) = v.remove("external_ids") {
                    ret.external_ids = parse_str_map(&ids);
                }
                if let Some(Value::Array(cfgs)) = v.remove("other_config") {
                    ret.other_config = parse_str_map(&cfgs);
                }
                if let Some(Value::Array(ports)) = v.remove("ports") {
                    ret.ports = parse_uuid_array(&ports);
                }
                if let Some(Value::Array(ports)) = v.remove("interfaces") {
                    ret.ports = parse_uuid_array(&ports);
                }
                for (key, value) in v.iter() {
                    ret.options.insert(key.to_string(), value.clone());
                }

                return Ok(ret);
            }
        }
        log::error!("{}", e);
        Err(e)
    }
}

pub(crate) fn parse_str_map(v: &[Value]) -> HashMap<String, String> {
    let mut ret = HashMap::new();
    if let Some(Value::String(value_type)) = v.first() {
        match value_type.as_str() {
            "map" => {
                if let Some(ids) = v.get(1).and_then(|i| i.as_array()) {
                    for kv in ids {
                        if let Some(kv) = kv.as_array() {
                            if let (
                                Some(Value::String(k)),
                                Some(Value::String(v)),
                            ) = (kv.first(), kv.get(1))
                            {
                                if k == NM_RESERVED_EXTERNAL_ID {
                                    continue;
                                }
                                ret.insert(k.to_string(), v.to_string());
                            }
                        }
                    }
                }
            }
            t => {
                log::warn!("Got unknown value type {t}: {v:?}");
            }
        }
    }
    ret
}

pub(crate) fn parse_uuid_array(v: &[Value]) -> Vec<String> {
    let mut ret = Vec::new();
    if let Some(Value::String(value_type)) = v.first() {
        match value_type.as_str() {
            "set" => {
                if let Some(vs) = v.get(1).and_then(|i| i.as_array()) {
                    for v in vs {
                        if let Some(kv) = v.as_array() {
                            if let (
                                Some(Value::String(k)),
                                Some(Value::String(v)),
                            ) = (kv.first(), kv.get(1))
                            {
                                if k != "uuid" {
                                    continue;
                                }
                                ret.push(v.to_string());
                            }
                        }
                    }
                }
            }
            "uuid" => {
                // Single item
                if let Some(Value::String(v)) = v.get(1) {
                    ret.push(v.to_string());
                }
            }
            t => {
                log::warn!("Got unknown value type {t}: {v:?}");
            }
        }
    }
    ret
}

fn check_transact_error(reply: Value) -> Result<Value, NmstateError> {
    if let Some(trans_replies) = reply.as_array() {
        for trans_reply in trans_replies {
            if let Some(error_type) = trans_reply
                .as_object()
                .and_then(|r| r.get("error"))
                .and_then(|e| e.as_str())
            {
                let error_detail = trans_reply
                    .as_object()
                    .and_then(|r| r.get("details"))
                    .and_then(|d| d.as_str())
                    .unwrap_or("unknown error");
                let e = NmstateError::new(
                    ErrorKind::PluginFailure,
                    format!(
                        "OVS DB JSON RPC error {error_type}: {error_detail}"
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
    }
    Ok(reply)
}
