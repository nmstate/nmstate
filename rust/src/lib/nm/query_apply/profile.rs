// SPDX-License-Identifier: Apache-2.0

use std::collections::{hash_map::Entry, HashMap};

use super::super::nm_dbus::{
    self, NmApi, NmConnection, NmSettingsConnectionFlag,
};
use super::super::{
    error::nm_error_to_nmstate,
    settings::{
        NM_SETTING_BOND_SETTING_NAME, NM_SETTING_BRIDGE_SETTING_NAME,
        NM_SETTING_OVS_BRIDGE_SETTING_NAME, NM_SETTING_OVS_PORT_SETTING_NAME,
        NM_SETTING_VETH_SETTING_NAME, NM_SETTING_VPN_SETTING_NAME,
        NM_SETTING_VRF_SETTING_NAME, NM_SETTING_WIRED_SETTING_NAME,
    },
};

use crate::NmstateError;

const ACTIVATION_RETRY_COUNT: usize = 6;
const ACTIVATION_RETRY_INTERVAL: u64 = 1;

pub(crate) const NM_SETTING_CONTROLLERS: [&str; 5] = [
    NM_SETTING_BOND_SETTING_NAME,
    NM_SETTING_BRIDGE_SETTING_NAME,
    NM_SETTING_OVS_BRIDGE_SETTING_NAME,
    NM_SETTING_OVS_PORT_SETTING_NAME,
    NM_SETTING_VRF_SETTING_NAME,
];

pub(crate) fn delete_exist_profiles(
    nm_api: &mut NmApi,
    exist_nm_conns: &[NmConnection],
    nm_conns: &[NmConnection],
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
        } else if nm_conn.iface_type() == Some(NM_SETTING_VPN_SETTING_NAME) {
            if let Some(name) = nm_conn.id() {
                // For VPN, the we use connection id
                changed_iface_name_types
                    .push((name, NM_SETTING_VPN_SETTING_NAME));
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
        } else if exist_nm_conn.iface_type()
            == Some(NM_SETTING_VPN_SETTING_NAME)
        {
            if let Some(i) = exist_nm_conn.id() {
                i
            } else {
                continue;
            }
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
    delete_profiles(nm_api, &uuids_to_delete)
}

pub(crate) fn save_nm_profiles(
    nm_api: &mut NmApi,
    nm_conns: &[NmConnection],
    memory_only: bool,
) -> Result<(), NmstateError> {
    for nm_conn in nm_conns {
        if nm_conn.obj_path.is_empty() {
            log::info!(
                "Creating connection UUID {:?}, ID {:?}, type {:?} name {:?}",
                nm_conn.uuid(),
                nm_conn.id(),
                nm_conn.iface_type(),
                nm_conn.iface_name(),
            );
        } else {
            log::info!(
                "Modifying connection UUID {:?}, ID {:?}, type {:?} name {:?}",
                nm_conn.uuid(),
                nm_conn.id(),
                nm_conn.iface_type(),
                nm_conn.iface_name(),
            );
        }
        nm_api
            .connection_add(nm_conn, memory_only)
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}

pub(crate) fn activate_nm_profiles(
    nm_api: &mut NmApi,
    nm_conns: &[NmConnection],
) -> Result<(), NmstateError> {
    let mut nm_conns = nm_conns.to_vec();
    let nm_acs = nm_api
        .active_connections_get()
        .map_err(nm_error_to_nmstate)?;
    let nm_ac_uuids: Vec<&str> =
        nm_acs.iter().map(|nm_ac| &nm_ac.uuid as &str).collect();

    for i in 1..ACTIVATION_RETRY_COUNT + 1 {
        if !nm_conns.is_empty() {
            let remain_nm_conns = _activate_nm_profiles(
                nm_api,
                nm_conns.as_slice(),
                nm_ac_uuids.as_slice(),
            )?;
            if remain_nm_conns.is_empty() {
                break;
            }
            if i == ACTIVATION_RETRY_COUNT {
                return Err(remain_nm_conns[0].1.clone());
            }
            nm_conns.clear();
            for (remain_nm_conn, e) in remain_nm_conns {
                log::info!("Got activation failure {e}");
                nm_conns.push(remain_nm_conn.clone());
            }
            let wait_internal = ACTIVATION_RETRY_INTERVAL * (1 << i);
            log::info!("Will retry activation {wait_internal} seconds");
            for _ in 0..wait_internal {
                nm_api
                    .extend_timeout_if_required()
                    .map_err(nm_error_to_nmstate)?;
                std::thread::sleep(std::time::Duration::from_secs(1));
            }
        } else {
            break;
        }
    }
    Ok(())
}

// Return list of activation failed `NmConnection` which we can retry
fn _activate_nm_profiles(
    nm_api: &mut NmApi,
    nm_conns: &[NmConnection],
    nm_ac_uuids: &[&str],
) -> Result<Vec<(NmConnection, NmstateError)>, NmstateError> {
    // Contain a list of `(iface_name, nm_iface_type)`.
    let mut new_controllers: Vec<(&str, &str)> = Vec::new();
    let mut failed_nm_conns: Vec<(NmConnection, NmstateError)> = Vec::new();
    for nm_conn in nm_conns.iter().filter(|c| {
        c.iface_type().map(|t| NM_SETTING_CONTROLLERS.contains(&t))
            == Some(true)
    }) {
        if let Some(uuid) = nm_conn.uuid() {
            log::info!(
                "Activating connection {}: {}/{}",
                uuid,
                nm_conn.iface_name().unwrap_or(""),
                nm_conn.iface_type().unwrap_or("")
            );
            if nm_ac_uuids.contains(&uuid) {
                if let Err(e) = reapply_or_activate(nm_api, nm_conn) {
                    if e.kind().can_retry() {
                        failed_nm_conns.push((nm_conn.clone(), e));
                    } else {
                        return Err(e);
                    }
                }
            } else {
                new_controllers.push((
                    nm_conn.iface_name().unwrap_or(""),
                    nm_conn.iface_type().unwrap_or(""),
                ));
                if let Err(e) = nm_api
                    .connection_activate(uuid)
                    .map_err(nm_error_to_nmstate)
                {
                    if e.kind().can_retry() {
                        failed_nm_conns.push((nm_conn.clone(), e));
                    } else {
                        return Err(e);
                    }
                }
            }
        }
    }
    for nm_conn in nm_conns.iter().filter(|c| {
        c.iface_type().map(|t| NM_SETTING_CONTROLLERS.contains(&t))
            != Some(true)
    }) {
        if let Some(uuid) = nm_conn.uuid() {
            if nm_ac_uuids.contains(&uuid) {
                log::info!(
                    "Reapplying connection {}: {}/{}",
                    uuid,
                    nm_conn.iface_name().unwrap_or(""),
                    nm_conn.iface_type().unwrap_or("")
                );
                if let Err(e) = reapply_or_activate(nm_api, nm_conn) {
                    if e.kind().can_retry() {
                        failed_nm_conns.push((nm_conn.clone(), e));
                    } else {
                        return Err(e);
                    }
                }
            } else {
                if let (Some(ctrller), Some(ctrller_type)) =
                    (nm_conn.controller(), nm_conn.controller_type())
                {
                    if nm_conn.iface_type() != Some("ovs-interface") {
                        // OVS port does not do auto port activation.
                        if new_controllers.contains(&(ctrller, ctrller_type))
                            && ctrller_type != "ovs-port"
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
                if let Err(e) = nm_api
                    .connection_activate(uuid)
                    .map_err(nm_error_to_nmstate)
                {
                    if e.kind().can_retry() {
                        failed_nm_conns.push((nm_conn.clone(), e));
                    } else {
                        return Err(e);
                    }
                }
            }
        }
    }
    Ok(failed_nm_conns)
}

pub(crate) fn deactivate_nm_profiles(
    nm_api: &mut NmApi,
    nm_conns: &[NmConnection],
) -> Result<(), NmstateError> {
    for nm_conn in nm_conns {
        if let Some(uuid) = nm_conn.uuid() {
            log::info!(
                "Deactivating connection {}: {}/{}",
                uuid,
                nm_conn.iface_name().unwrap_or(""),
                nm_conn.iface_type().unwrap_or("")
            );
            if let Err(e) = nm_api.connection_deactivate(uuid) {
                if e.kind
                    != nm_dbus::ErrorKind::Manager(
                        nm_dbus::NmManagerError::ConnectionNotActive,
                    )
                {
                    return Err(nm_error_to_nmstate(e));
                }
            }
        }
    }
    Ok(())
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

pub(crate) fn delete_profiles(
    nm_api: &mut NmApi,
    uuids: &[&str],
) -> Result<(), NmstateError> {
    for uuid in uuids {
        nm_api
            .connection_delete(uuid)
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}

fn reapply_or_activate(
    nm_api: &mut NmApi,
    nm_conn: &NmConnection,
) -> Result<(), NmstateError> {
    if let Err(e) = nm_api.connection_reapply(nm_conn) {
        if let Some(uuid) = nm_conn.uuid() {
            log::info!(
                "Reapply operation failed on {} {} {uuid}, \
                reason: {}, retry on normal activation",
                nm_conn.iface_type().unwrap_or(""),
                nm_conn.iface_name().unwrap_or(""),
                e
            );
            nm_api
                .connection_activate(uuid)
                .map_err(nm_error_to_nmstate)?;
        }
    }
    Ok(())
}

pub(crate) fn is_uuid(value: &str) -> bool {
    uuid::Uuid::parse_str(value).is_ok()
}
