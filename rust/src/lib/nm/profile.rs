use std::collections::{hash_map::Entry, HashMap};
use std::time::Instant;

use super::nm_dbus::{NmApi, NmConnection, NmSettingsConnectionFlag};

use crate::{
    nm::checkpoint::{
        nm_checkpoint_timeout_extend, CHECKPOINT_ROLLBACK_TIMEOUT,
    },
    nm::error::nm_error_to_nmstate,
    nm::settings::{
        NM_SETTING_BOND_SETTING_NAME, NM_SETTING_BRIDGE_SETTING_NAME,
        NM_SETTING_OVS_BRIDGE_SETTING_NAME, NM_SETTING_OVS_PORT_SETTING_NAME,
        NM_SETTING_VETH_SETTING_NAME, NM_SETTING_VRF_SETTING_NAME,
        NM_SETTING_WIRED_SETTING_NAME,
    },
    NmstateError,
};

pub(crate) const NM_SETTING_CONTROLLERS: [&str; 5] = [
    NM_SETTING_BOND_SETTING_NAME,
    NM_SETTING_BRIDGE_SETTING_NAME,
    NM_SETTING_OVS_BRIDGE_SETTING_NAME,
    NM_SETTING_OVS_PORT_SETTING_NAME,
    NM_SETTING_VRF_SETTING_NAME,
];

pub(crate) fn delete_exist_profiles(
    nm_api: &NmApi,
    exist_nm_conns: &[NmConnection],
    nm_conns: &[NmConnection],
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let mut excluded_uuids: Vec<&str> = Vec::new();
    let mut changed_iface_name_types: Vec<(&str, &str)> = Vec::new();
    let mut uuids_to_delete = Vec::new();
    for nm_conn in nm_conns {
        if let Some(uuid) = nm_conn.uuid() {
            excluded_uuids.push(uuid);
        }
        if let Some(name) = nm_conn.iface_name() {
            if let Some(nm_iface_type) = nm_conn.iface_type() {
                changed_iface_name_types.push((name, nm_iface_type));
            }
        }
    }
    for exist_nm_conn in exist_nm_conns {
        let uuid = if let Some(u) = exist_nm_conn.uuid() {
            u
        } else {
            continue;
        };
        let iface_name = if let Some(i) = exist_nm_conn.iface_name() {
            i
        } else {
            continue;
        };
        let nm_iface_type = if let Some(t) = exist_nm_conn.iface_type() {
            t
        } else {
            continue;
        };
        // Volatile nm_conn will be automatically removed once deactivated.
        // Hence no need to deactivate.
        if exist_nm_conn
            .flags
            .contains(&NmSettingsConnectionFlag::Volatile)
        {
            continue;
        }
        if !excluded_uuids.contains(&uuid)
            && changed_iface_name_types.contains(&(iface_name, nm_iface_type))
        {
            if let Some(uuid) = exist_nm_conn.uuid() {
                uuids_to_delete.push(uuid);
                log::info!(
                    "Deleting existing connection \
                UUID {}, id {:?} type {:?} name {:?}",
                    uuid,
                    exist_nm_conn.id(),
                    exist_nm_conn.iface_type(),
                    exist_nm_conn.iface_name(),
                );
            }
        }
    }
    delete_profiles(nm_api, &uuids_to_delete, checkpoint)
}

pub(crate) fn save_nm_profiles(
    nm_api: &NmApi,
    nm_conns: &[NmConnection],
    checkpoint: &str,
    memory_only: bool,
) -> Result<(), NmstateError> {
    let mut now = Instant::now();
    for nm_conn in nm_conns {
        extend_timeout_if_required(&mut now, checkpoint)?;
        log::info!(
            "Creating/Modifying connection \
            UUID {:?}, ID {:?}, type {:?} name {:?}",
            nm_conn.uuid(),
            nm_conn.id(),
            nm_conn.iface_type(),
            nm_conn.iface_name(),
        );
        nm_api
            .connection_add(nm_conn, memory_only)
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}

pub(crate) fn activate_nm_profiles(
    nm_api: &NmApi,
    nm_conns: &[NmConnection],
    nm_ac_uuids: &[&str],
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let mut now = Instant::now();
    let mut new_controllers: Vec<&str> = Vec::new();
    for nm_conn in nm_conns.iter().filter(|c| {
        c.iface_type().map(|t| NM_SETTING_CONTROLLERS.contains(&t))
            == Some(true)
    }) {
        extend_timeout_if_required(&mut now, checkpoint)?;
        if let Some(uuid) = nm_conn.uuid() {
            log::info!(
                "Activating connection {}: {}/{}",
                uuid,
                nm_conn.iface_name().unwrap_or(""),
                nm_conn.iface_type().unwrap_or("")
            );
            if nm_ac_uuids.contains(&uuid) {
                if let Err(e) = nm_api.connection_reapply(nm_conn) {
                    log::info!(
                        "Reapply operation failed trying activation, \
                        reason: {}, retry on normal activation",
                        e
                    );
                    nm_api
                        .connection_activate(uuid)
                        .map_err(nm_error_to_nmstate)?;
                }
            } else {
                new_controllers.push(uuid);
                nm_api
                    .connection_activate(uuid)
                    .map_err(nm_error_to_nmstate)?;
            }
        }
    }
    for nm_conn in nm_conns.iter().filter(|c| {
        c.iface_type().map(|t| NM_SETTING_CONTROLLERS.contains(&t))
            != Some(true)
    }) {
        extend_timeout_if_required(&mut now, checkpoint)?;

        if let Some(uuid) = nm_conn.uuid() {
            if nm_ac_uuids.contains(&uuid) {
                log::info!(
                    "Reapplying connection {}: {}/{}",
                    uuid,
                    nm_conn.iface_name().unwrap_or(""),
                    nm_conn.iface_type().unwrap_or("")
                );
                if let Err(e) = nm_api.connection_reapply(nm_conn) {
                    log::info!(
                        "Reapply operation failed trying activation, \
                        reason: {}, retry on normal activation",
                        e
                    );
                    log::info!(
                        "Activating connection {}: {}/{}",
                        uuid,
                        nm_conn.iface_name().unwrap_or(""),
                        nm_conn.iface_type().unwrap_or("")
                    );
                    nm_api
                        .connection_activate(uuid)
                        .map_err(nm_error_to_nmstate)?;
                }
            } else {
                if let Some(ctrller) = nm_conn.controller() {
                    if nm_conn.iface_type() != Some("ovs-interface") {
                        // OVS port does not do auto port activation.
                        if new_controllers.contains(&ctrller)
                            && nm_conn.controller_type() != Some("ovs-port")
                        {
                            log::info!(
                                "Skip connection activation as its \
                                controller already activated its ports: \
                                {}: {}/{}",
                                uuid,
                                nm_conn.iface_name().unwrap_or(""),
                                nm_conn.iface_type().unwrap_or("")
                            );
                            continue;
                        }
                    }
                }
                log::info!(
                    "Activating connection {}: {}/{}",
                    uuid,
                    nm_conn.iface_name().unwrap_or(""),
                    nm_conn.iface_type().unwrap_or("")
                );
                nm_api
                    .connection_activate(uuid)
                    .map_err(nm_error_to_nmstate)?;
            }
        }
    }
    Ok(())
}

pub(crate) fn deactivate_nm_profiles(
    nm_api: &NmApi,
    nm_conns: &[&NmConnection],
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let mut now = Instant::now();
    for nm_conn in nm_conns {
        extend_timeout_if_required(&mut now, checkpoint)?;
        if let Some(uuid) = nm_conn.uuid() {
            log::info!(
                "Deactivating connection {}: {}/{}",
                uuid,
                nm_conn.iface_name().unwrap_or(""),
                nm_conn.iface_type().unwrap_or("")
            );
            nm_api
                .connection_deactivate(uuid)
                .map_err(nm_error_to_nmstate)?;
        }
    }
    Ok(())
}

pub(crate) fn extend_timeout_if_required(
    now: &mut Instant,
    checkpoint: &str,
) -> Result<(), NmstateError> {
    // Only extend the timeout when only half of it elapsed
    if now.elapsed().as_secs() >= CHECKPOINT_ROLLBACK_TIMEOUT as u64 / 2 {
        log::debug!("Extending checkpoint timeout");
        nm_checkpoint_timeout_extend(checkpoint, CHECKPOINT_ROLLBACK_TIMEOUT)?;
        *now = Instant::now();
    }
    Ok(())
}

pub(crate) fn create_index_for_nm_conns_by_ctrler_type(
    nm_conns: &[NmConnection],
) -> HashMap<(&str, &str), Vec<&NmConnection>> {
    let mut ret: HashMap<(&str, &str), Vec<&NmConnection>> = HashMap::new();
    for nm_conn in nm_conns {
        let ctrl_name = if let Some(c) = nm_conn.controller() {
            c
        } else {
            continue;
        };
        let nm_ctrl_type = if let Some(c) = nm_conn.controller_type() {
            c
        } else {
            continue;
        };
        match ret.entry((ctrl_name, nm_ctrl_type)) {
            Entry::Occupied(o) => {
                o.into_mut().push(nm_conn);
            }
            Entry::Vacant(v) => {
                v.insert(vec![nm_conn]);
            }
        };
    }
    ret
}

pub(crate) fn create_index_for_nm_conns_by_name_type(
    nm_conns: &[NmConnection],
) -> HashMap<(&str, &str), Vec<&NmConnection>> {
    let mut ret: HashMap<(&str, &str), Vec<&NmConnection>> = HashMap::new();
    for nm_conn in nm_conns {
        if let Some(iface_name) = nm_conn.iface_name() {
            if let Some(nm_iface_type) = nm_conn.iface_type() {
                if nm_iface_type == NM_SETTING_VETH_SETTING_NAME {
                    match ret.entry((iface_name, NM_SETTING_WIRED_SETTING_NAME))
                    {
                        Entry::Occupied(o) => {
                            o.into_mut().push(nm_conn);
                        }
                        Entry::Vacant(v) => {
                            v.insert(vec![nm_conn]);
                        }
                    };
                }
                if nm_iface_type == NM_SETTING_WIRED_SETTING_NAME {
                    match ret.entry((iface_name, NM_SETTING_VETH_SETTING_NAME))
                    {
                        Entry::Occupied(o) => {
                            o.into_mut().push(nm_conn);
                        }
                        Entry::Vacant(v) => {
                            v.insert(vec![nm_conn]);
                        }
                    };
                }
                match ret.entry((iface_name, nm_iface_type)) {
                    Entry::Occupied(o) => {
                        o.into_mut().push(nm_conn);
                    }
                    Entry::Vacant(v) => {
                        v.insert(vec![nm_conn]);
                    }
                };
            }
        }
    }
    ret
}

pub(crate) fn get_port_nm_conns<'a>(
    nm_conn: &'a NmConnection,
    nm_conns_ctrler_type_index: &HashMap<
        (&'a str, &'a str),
        Vec<&'a NmConnection>,
    >,
) -> Vec<&'a NmConnection> {
    let mut ret: Vec<&NmConnection> = Vec::new();
    if let Some(nm_iface_type) = nm_conn.iface_type() {
        if let Some(uuid) = nm_conn.uuid() {
            if let Some(port_nm_conns) =
                nm_conns_ctrler_type_index.get(&(uuid, nm_iface_type))
            {
                for port_nm_conn in port_nm_conns {
                    ret.push(port_nm_conn);
                    if port_nm_conn.iface_type() == Some("ovs-port") {
                        for ovs_iface_nm_conn in get_port_nm_conns(
                            port_nm_conn,
                            nm_conns_ctrler_type_index,
                        ) {
                            ret.push(ovs_iface_nm_conn)
                        }
                    }
                }
            }
        }

        if let Some(name) = nm_conn.iface_name() {
            if let Some(port_nm_conns) =
                nm_conns_ctrler_type_index.get(&(name, nm_iface_type))
            {
                for port_nm_conn in port_nm_conns {
                    ret.push(port_nm_conn);
                    if port_nm_conn.iface_type() == Some("ovs-port") {
                        for ovs_iface_nm_conn in get_port_nm_conns(
                            port_nm_conn,
                            nm_conns_ctrler_type_index,
                        ) {
                            ret.push(ovs_iface_nm_conn)
                        }
                    }
                }
            }
        }
    }
    ret
}

pub(crate) fn delete_profiles(
    nm_api: &NmApi,
    uuids: &[&str],
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let mut now = Instant::now();
    for uuid in uuids {
        extend_timeout_if_required(&mut now, checkpoint)?;
        nm_api
            .connection_delete(uuid)
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}
