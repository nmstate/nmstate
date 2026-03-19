// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{
    Interface, InterfaceState, InterfaceType, MergedNetworkState, NmstateError,
    OvsBridgeInterface,
    ovsdb::{
        OVS_DB_NAME, OvsDbCondition, OvsDbConnection, OvsDbDelete, OvsDbInsert,
        OvsDbMethodTransact, OvsDbMutate, OvsDbMutation, OvsDbOperation,
        OvsDbUpdate, build_set_value, named_uuid_ref, uuid_ref,
    },
};

const GLOBAL_CONFIG_TABLE: &str = "Open_vSwitch";

pub(crate) async fn ovsdb_apply_bridges(
    merged_state: &MergedNetworkState,
) -> Result<(), NmstateError> {
    for iface in merged_state.interfaces.iter() {
        let des_iface = if let Some(ref i) = iface.for_apply {
            i
        } else if let Some(ref i) = iface.desired {
            i
        } else {
            continue;
        };
        if des_iface.base_iface().iface_type != InterfaceType::OvsBridge {
            continue;
        }
        let br_name = &des_iface.base_iface().name;

        if des_iface.base_iface().state == InterfaceState::Absent {
            if iface.current.is_some() {
                ovsdb_delete_bridge(br_name).await?;
            }
        } else if des_iface.base_iface().state == InterfaceState::Up {
            if let Interface::OvsBridge(br_iface) = des_iface {
                if let Some(Interface::OvsBridge(cur_br_iface)) =
                    iface.current.as_ref()
                {
                    ovsdb_update_bridge(br_iface, cur_br_iface).await?;
                } else {
                    ovsdb_create_bridge(br_iface).await?;
                }
            }
        }
    }
    Ok(())
}

async fn ovsdb_create_bridge(
    br_iface: &OvsBridgeInterface,
) -> Result<(), NmstateError> {
    let mut cli = OvsDbConnection::new().await?;
    let mut ops = Vec::new();
    let br_name = &br_iface.base.name;

    let mut port_uuid_refs = Vec::new();

    if let Some(br_conf) = &br_iface.bridge {
        if let Some(port_confs) = &br_conf.ports {
            for port_conf in port_confs {
                let port_uuid_name =
                    format!("port_{}", port_conf.name.replace('-', "_"));

                if let Some(bond_conf) = &port_conf.bond {
                    let mut iface_uuid_refs = Vec::new();
                    if let Some(bond_ports) = &bond_conf.ports {
                        for bond_port in bond_ports {
                            let iface_uuid_name = format!(
                                "iface_{}",
                                bond_port.name.replace('-', "_")
                            );
                            let mut iface_row = HashMap::new();
                            iface_row.insert(
                                "name".to_string(),
                                serde_json::Value::String(
                                    bond_port.name.clone(),
                                ),
                            );
                            ops.push(OvsDbOperation::Insert(OvsDbInsert {
                                table: "Interface".to_string(),
                                row: iface_row,
                                uuid_name: Some(iface_uuid_name.clone()),
                            }));
                            iface_uuid_refs
                                .push(named_uuid_ref(&iface_uuid_name));
                        }
                    }

                    let mut port_row = HashMap::new();
                    port_row.insert(
                        "name".to_string(),
                        serde_json::Value::String(port_conf.name.clone()),
                    );
                    port_row.insert(
                        "interfaces".to_string(),
                        build_set_value(&iface_uuid_refs),
                    );
                    if let Some(ref mode) = bond_conf.mode {
                        port_row.insert(
                            "bond_mode".to_string(),
                            serde_json::Value::String(mode.to_string()),
                        );
                    }
                    if let Some(updelay) = bond_conf.bond_updelay {
                        port_row.insert(
                            "bond_updelay".to_string(),
                            serde_json::Value::Number(updelay.into()),
                        );
                    }
                    if let Some(downdelay) = bond_conf.bond_downdelay {
                        port_row.insert(
                            "bond_downdelay".to_string(),
                            serde_json::Value::Number(downdelay.into()),
                        );
                    }
                    ops.push(OvsDbOperation::Insert(OvsDbInsert {
                        table: "Port".to_string(),
                        row: port_row,
                        uuid_name: Some(port_uuid_name.clone()),
                    }));
                } else {
                    // Non-bond port: single interface with same name
                    let iface_uuid_name =
                        format!("iface_{}", port_conf.name.replace('-', "_"));
                    let mut iface_row = HashMap::new();
                    iface_row.insert(
                        "name".to_string(),
                        serde_json::Value::String(port_conf.name.clone()),
                    );
                    iface_row.insert(
                        "type".to_string(),
                        serde_json::Value::String("internal".to_string()),
                    );
                    ops.push(OvsDbOperation::Insert(OvsDbInsert {
                        table: "Interface".to_string(),
                        row: iface_row,
                        uuid_name: Some(iface_uuid_name.clone()),
                    }));

                    let mut port_row = HashMap::new();
                    port_row.insert(
                        "name".to_string(),
                        serde_json::Value::String(port_conf.name.clone()),
                    );
                    port_row.insert(
                        "interfaces".to_string(),
                        named_uuid_ref(&iface_uuid_name),
                    );
                    ops.push(OvsDbOperation::Insert(OvsDbInsert {
                        table: "Port".to_string(),
                        row: port_row,
                        uuid_name: Some(port_uuid_name.clone()),
                    }));
                }
                port_uuid_refs.push(named_uuid_ref(&port_uuid_name));
            }
        }
    }

    // Build Bridge row
    let bridge_uuid_name = format!("bridge_{}", br_name.replace('-', "_"));
    let mut bridge_row = HashMap::new();
    bridge_row.insert(
        "name".to_string(),
        serde_json::Value::String(br_name.clone()),
    );
    if !port_uuid_refs.is_empty() {
        bridge_row
            .insert("ports".to_string(), build_set_value(&port_uuid_refs));
    }

    if let Some(br_conf) = &br_iface.bridge {
        if let Some(ref options) = br_conf.options {
            if let Some(ref stp) = options.stp {
                if let Some(enabled) = stp.enabled {
                    bridge_row.insert(
                        "stp_enable".to_string(),
                        serde_json::Value::Bool(enabled),
                    );
                }
            }
            if let Some(rstp) = options.rstp {
                bridge_row.insert(
                    "rstp_enable".to_string(),
                    serde_json::Value::Bool(rstp),
                );
            }
            if let Some(mcast) = options.mcast_snooping_enable {
                bridge_row.insert(
                    "mcast_snooping_enable".to_string(),
                    serde_json::Value::Bool(mcast),
                );
            }
            if let Some(ref fail_mode) = options.fail_mode {
                if !fail_mode.is_empty() {
                    bridge_row.insert(
                        "fail_mode".to_string(),
                        serde_json::Value::String(fail_mode.clone()),
                    );
                }
            }
        }
    }

    ops.push(OvsDbOperation::Insert(OvsDbInsert {
        table: "Bridge".to_string(),
        row: bridge_row,
        uuid_name: Some(bridge_uuid_name.clone()),
    }));

    // MUTATE Open_vSwitch to add bridge
    ops.push(OvsDbOperation::Mutate(OvsDbMutate {
        table: GLOBAL_CONFIG_TABLE.to_string(),
        conditions: vec![],
        mutations: vec![OvsDbMutation {
            column: "bridges".to_string(),
            mutator: "insert".to_string(),
            value: named_uuid_ref(&bridge_uuid_name),
        }],
    }));

    cli.transact(&OvsDbMethodTransact {
        db_name: OVS_DB_NAME.to_string(),
        operations: ops,
    })
    .await?;
    log::info!("Created OVS bridge {br_name} via OVSDB");
    Ok(())
}

async fn ovsdb_delete_bridge(br_name: &str) -> Result<(), NmstateError> {
    let mut cli = OvsDbConnection::new().await?;

    // Get the bridge UUID and its port UUIDs
    let bridges = cli.get_ovs_bridges().await?;
    let (bridge_uuid, bridge_entry) =
        match bridges.iter().find(|(_, e)| e.name == br_name) {
            Some((uuid, entry)) => (uuid.clone(), entry),
            None => {
                log::warn!(
                    "OVS bridge {br_name} not found in OVSDB, skipping delete"
                );
                return Ok(());
            }
        };

    let port_uuids = bridge_entry.ports.clone();

    // Get interface UUIDs from ports
    let all_ports = cli.get_ovs_ports().await?;
    let mut iface_uuids = Vec::new();
    for port_uuid in &port_uuids {
        if let Some(port_entry) = all_ports.get(port_uuid) {
            iface_uuids.extend(port_entry.ports.clone());
        }
    }

    let mut ops = Vec::new();

    // DELETE interfaces
    for iface_uuid in &iface_uuids {
        ops.push(OvsDbOperation::Delete(OvsDbDelete {
            table: "Interface".to_string(),
            conditions: vec![OvsDbCondition {
                column: "_uuid".to_string(),
                function: "==".to_string(),
                value: uuid_ref(iface_uuid),
            }],
        }));
    }

    // DELETE ports
    for port_uuid in &port_uuids {
        ops.push(OvsDbOperation::Delete(OvsDbDelete {
            table: "Port".to_string(),
            conditions: vec![OvsDbCondition {
                column: "_uuid".to_string(),
                function: "==".to_string(),
                value: uuid_ref(port_uuid),
            }],
        }));
    }

    // DELETE bridge
    ops.push(OvsDbOperation::Delete(OvsDbDelete {
        table: "Bridge".to_string(),
        conditions: vec![OvsDbCondition {
            column: "_uuid".to_string(),
            function: "==".to_string(),
            value: uuid_ref(&bridge_uuid),
        }],
    }));

    // MUTATE Open_vSwitch to remove bridge
    ops.push(OvsDbOperation::Mutate(OvsDbMutate {
        table: GLOBAL_CONFIG_TABLE.to_string(),
        conditions: vec![],
        mutations: vec![OvsDbMutation {
            column: "bridges".to_string(),
            mutator: "delete".to_string(),
            value: uuid_ref(&bridge_uuid),
        }],
    }));

    cli.transact(&OvsDbMethodTransact {
        db_name: OVS_DB_NAME.to_string(),
        operations: ops,
    })
    .await?;
    log::info!("Deleted OVS bridge {br_name} via OVSDB");
    Ok(())
}

async fn ovsdb_update_bridge(
    desired_br: &OvsBridgeInterface,
    current_br: &OvsBridgeInterface,
) -> Result<(), NmstateError> {
    let mut cli = OvsDbConnection::new().await?;
    let br_name = &desired_br.base.name;
    let mut ops = Vec::new();

    let name_condition = OvsDbCondition {
        column: "name".to_string(),
        function: "==".to_string(),
        value: serde_json::Value::String(br_name.clone()),
    };

    let mut bridge_row_updates: HashMap<String, serde_json::Value> =
        HashMap::new();

    if let Some(ref desired_conf) = desired_br.bridge {
        if let Some(ref options) = desired_conf.options {
            if let Some(ref stp) = options.stp {
                if let Some(enabled) = stp.enabled {
                    bridge_row_updates.insert(
                        "stp_enable".to_string(),
                        serde_json::Value::Bool(enabled),
                    );
                }
            }
            if let Some(rstp) = options.rstp {
                bridge_row_updates.insert(
                    "rstp_enable".to_string(),
                    serde_json::Value::Bool(rstp),
                );
            }
            if let Some(mcast) = options.mcast_snooping_enable {
                bridge_row_updates.insert(
                    "mcast_snooping_enable".to_string(),
                    serde_json::Value::Bool(mcast),
                );
            }
            if let Some(ref fail_mode) = options.fail_mode {
                if !fail_mode.is_empty() {
                    bridge_row_updates.insert(
                        "fail_mode".to_string(),
                        serde_json::Value::String(fail_mode.clone()),
                    );
                }
            }
        }

        // Handle port changes
        let desired_ports = desired_conf
            .ports
            .as_ref()
            .map(|p| p.as_slice())
            .unwrap_or(&[]);
        let current_ports = current_br
            .bridge
            .as_ref()
            .and_then(|c| c.ports.as_ref())
            .map(|p| p.as_slice())
            .unwrap_or(&[]);

        let desired_port_names: Vec<&str> =
            desired_ports.iter().map(|p| p.name.as_str()).collect();
        let current_port_names: Vec<&str> =
            current_ports.iter().map(|p| p.name.as_str()).collect();

        // Ports to add
        let ports_to_add: Vec<_> = desired_ports
            .iter()
            .filter(|p| !current_port_names.contains(&p.name.as_str()))
            .collect();

        // Ports to remove
        let ports_to_remove: Vec<_> = current_ports
            .iter()
            .filter(|p| !desired_port_names.contains(&p.name.as_str()))
            .collect();

        if !ports_to_remove.is_empty() {
            let all_ports = cli.get_ovs_ports().await?;
            for port_conf in &ports_to_remove {
                if let Some((port_uuid, port_entry)) =
                    all_ports.iter().find(|(_, e)| e.name == port_conf.name)
                {
                    // Delete interfaces of this port
                    for iface_uuid in &port_entry.ports {
                        ops.push(OvsDbOperation::Delete(OvsDbDelete {
                            table: "Interface".to_string(),
                            conditions: vec![OvsDbCondition {
                                column: "_uuid".to_string(),
                                function: "==".to_string(),
                                value: uuid_ref(iface_uuid),
                            }],
                        }));
                    }

                    // MUTATE bridge to remove port
                    ops.push(OvsDbOperation::Mutate(OvsDbMutate {
                        table: "Bridge".to_string(),
                        conditions: vec![name_condition.clone()],
                        mutations: vec![OvsDbMutation {
                            column: "ports".to_string(),
                            mutator: "delete".to_string(),
                            value: uuid_ref(port_uuid),
                        }],
                    }));

                    // Delete port row
                    ops.push(OvsDbOperation::Delete(OvsDbDelete {
                        table: "Port".to_string(),
                        conditions: vec![OvsDbCondition {
                            column: "_uuid".to_string(),
                            function: "==".to_string(),
                            value: uuid_ref(port_uuid),
                        }],
                    }));
                }
            }
        }

        // Add ports
        for port_conf in &ports_to_add {
            let port_uuid_name =
                format!("port_{}", port_conf.name.replace('-', "_"));

            if let Some(bond_conf) = &port_conf.bond {
                let mut iface_uuid_refs = Vec::new();
                if let Some(bond_ports) = &bond_conf.ports {
                    for bond_port in bond_ports {
                        let iface_uuid_name = format!(
                            "iface_{}",
                            bond_port.name.replace('-', "_")
                        );
                        let mut iface_row = HashMap::new();
                        iface_row.insert(
                            "name".to_string(),
                            serde_json::Value::String(bond_port.name.clone()),
                        );
                        ops.push(OvsDbOperation::Insert(OvsDbInsert {
                            table: "Interface".to_string(),
                            row: iface_row,
                            uuid_name: Some(iface_uuid_name.clone()),
                        }));
                        iface_uuid_refs.push(named_uuid_ref(&iface_uuid_name));
                    }
                }

                let mut port_row = HashMap::new();
                port_row.insert(
                    "name".to_string(),
                    serde_json::Value::String(port_conf.name.clone()),
                );
                port_row.insert(
                    "interfaces".to_string(),
                    build_set_value(&iface_uuid_refs),
                );
                if let Some(ref mode) = bond_conf.mode {
                    port_row.insert(
                        "bond_mode".to_string(),
                        serde_json::Value::String(mode.to_string()),
                    );
                }
                ops.push(OvsDbOperation::Insert(OvsDbInsert {
                    table: "Port".to_string(),
                    row: port_row,
                    uuid_name: Some(port_uuid_name.clone()),
                }));
            } else {
                let iface_uuid_name =
                    format!("iface_{}", port_conf.name.replace('-', "_"));
                let mut iface_row = HashMap::new();
                iface_row.insert(
                    "name".to_string(),
                    serde_json::Value::String(port_conf.name.clone()),
                );
                iface_row.insert(
                    "type".to_string(),
                    serde_json::Value::String("internal".to_string()),
                );
                ops.push(OvsDbOperation::Insert(OvsDbInsert {
                    table: "Interface".to_string(),
                    row: iface_row,
                    uuid_name: Some(iface_uuid_name.clone()),
                }));

                let mut port_row = HashMap::new();
                port_row.insert(
                    "name".to_string(),
                    serde_json::Value::String(port_conf.name.clone()),
                );
                port_row.insert(
                    "interfaces".to_string(),
                    named_uuid_ref(&iface_uuid_name),
                );
                ops.push(OvsDbOperation::Insert(OvsDbInsert {
                    table: "Port".to_string(),
                    row: port_row,
                    uuid_name: Some(port_uuid_name.clone()),
                }));
            }

            // MUTATE bridge to add port
            ops.push(OvsDbOperation::Mutate(OvsDbMutate {
                table: "Bridge".to_string(),
                conditions: vec![name_condition.clone()],
                mutations: vec![OvsDbMutation {
                    column: "ports".to_string(),
                    mutator: "insert".to_string(),
                    value: named_uuid_ref(&port_uuid_name),
                }],
            }));
        }
    }

    if !bridge_row_updates.is_empty() {
        ops.push(OvsDbOperation::Update(OvsDbUpdate {
            table: "Bridge".to_string(),
            conditions: vec![name_condition],
            row: bridge_row_updates,
        }));
    }

    if !ops.is_empty() {
        cli.transact(&OvsDbMethodTransact {
            db_name: OVS_DB_NAME.to_string(),
            operations: ops,
        })
        .await?;
        log::info!("Updated OVS bridge {br_name} via OVSDB");
    }
    Ok(())
}
