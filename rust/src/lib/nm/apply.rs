use std::collections::HashMap;

use log::info;
use nm_dbus::{NmApi, NmDeviceState};

use crate::{
    nm::checkpoint::nm_checkpoint_timeout_extend,
    nm::connection::{
        create_index_for_nm_conns, iface_to_nm_connection, iface_type_to_nm,
    },
    nm::device::create_index_for_nm_devs,
    nm::error::nm_error_to_nmstate,
    nm::profile::delete_exist_profiles,
    InterfaceType, NetworkState, NmstateError,
};

// We only adjust timeout for every 20 profile additions.
const TIMEOUT_ADJUST_PROFILE_ADDTION_GROUP_SIZE: usize = 20;
const TIMEOUT_SECONDS_FOR_PROFILE_ADDTION: u32 = 60;
const TIMEOUT_SECONDS_FOR_PROFILE_ACTIVATION: u32 = 60;

pub(crate) fn nm_apply(
    add_net_state: &NetworkState,
    chg_net_state: &NetworkState,
    del_net_state: &NetworkState,
    _cur_net_state: &NetworkState,
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let nm_api = NmApi::new().map_err(nm_error_to_nmstate)?;

    delete_net_state(&nm_api, del_net_state)?;
    apply_single_state(&nm_api, add_net_state, checkpoint)?;
    apply_single_state(&nm_api, chg_net_state, checkpoint)?;
    Ok(())
}

fn delete_net_state(
    nm_api: &NmApi,
    net_state: &NetworkState,
) -> Result<(), NmstateError> {
    // TODO: Should we remove inactive connections also?
    let nm_conns = nm_api.connections_get().map_err(nm_error_to_nmstate)?;
    let nm_devs = nm_api.devices_get().map_err(nm_error_to_nmstate)?;

    let nm_conns_indexed = create_index_for_nm_conns(&nm_conns);
    let nm_devs_indexed = create_index_for_nm_devs(&nm_devs);

    for iface in &(net_state.interfaces.to_vec()) {
        if !iface.is_absent() {
            continue;
        }
        let nm_iface_type = iface_type_to_nm(&iface.iface_type())?;
        // Delete all existing connections for this interface
        if let Some(nm_conns) =
            nm_conns_indexed.get(&(iface.name().to_string(), nm_iface_type))
        {
            for nm_conn in nm_conns {
                if let Some(uuid) = nm_conn.uuid() {
                    info!(
                        "Deleting NM connection for absent interface \
                            {}/{}: {:?}",
                        &iface.name(),
                        &iface.iface_type(),
                        nm_conn
                    );
                    nm_api
                        .connection_delete(uuid)
                        .map_err(nm_error_to_nmstate)?;
                }
            }
        }
        // Delete unmanaged software(virtual) interface
        if iface.is_virtual() {
            if let Some(nm_dev) = nm_devs_indexed.get(&(
                iface.name().to_string(),
                iface.iface_type().to_string(),
            )) {
                if nm_dev.state == NmDeviceState::Unmanaged {
                    info!(
                        "Deleting NM unmanaged interface {}/{}: {}",
                        &iface.name(),
                        &iface.iface_type(),
                        &nm_dev.obj_path
                    );
                    nm_api
                        .device_delete(&nm_dev.obj_path)
                        .map_err(nm_error_to_nmstate)?;
                }
            }
        }
    }
    Ok(())
}

fn apply_single_state(
    nm_api: &NmApi,
    net_state: &NetworkState,
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let mut nm_conn_uuids: Vec<String> = Vec::new();
    let mut ports: HashMap<String, (String, InterfaceType)> = HashMap::new();

    let exist_nm_conns =
        nm_api.connections_get().map_err(nm_error_to_nmstate)?;
    let nm_acs = nm_api
        .active_connections_get()
        .map_err(nm_error_to_nmstate)?;
    let nm_ac_uuids: Vec<&str> =
        nm_acs.iter().map(|nm_ac| &nm_ac.uuid as &str).collect();

    let ifaces = net_state.interfaces.to_vec();
    for iface in &ifaces {
        if let Some(iface_ports) = iface.ports() {
            for port_name in iface_ports {
                ports.insert(
                    port_name.to_string(),
                    (iface.name().to_string(), iface.iface_type().clone()),
                );
            }
        }
    }

    for (index, iface) in ifaces.iter().enumerate() {
        // Only extend the timeout every
        // TIMEOUT_ADJUST_PROFILE_ADDTION_GROUP_SIZE profile addition.
        if index % TIMEOUT_ADJUST_PROFILE_ADDTION_GROUP_SIZE
            == TIMEOUT_ADJUST_PROFILE_ADDTION_GROUP_SIZE - 1
        {
            nm_checkpoint_timeout_extend(
                checkpoint,
                TIMEOUT_SECONDS_FOR_PROFILE_ADDTION,
            )?;
        }
        if iface.iface_type() != InterfaceType::Unknown && iface.is_up() {
            let (uuid, nm_conn) =
                iface_to_nm_connection(iface, &exist_nm_conns, &nm_ac_uuids)?;
            info!("Creating connection {:?}", nm_conn);
            nm_api
                .connection_add(&nm_conn)
                .map_err(nm_error_to_nmstate)?;

            delete_exist_profiles(
                nm_api,
                &exist_nm_conns,
                iface.name(),
                &iface.iface_type(),
                &uuid,
            )?;
            nm_conn_uuids.push(uuid);
        }
    }
    for nm_conn_uuid in &nm_conn_uuids {
        nm_checkpoint_timeout_extend(
            checkpoint,
            TIMEOUT_SECONDS_FOR_PROFILE_ACTIVATION,
        )?;
        info!("Activating connection {}", nm_conn_uuid);
        if let Err(e) = nm_api.connection_reapply(nm_conn_uuid) {
            info!("Reapply operation failed trying activation, reason: {}", e);
            nm_api
                .connection_activate(nm_conn_uuid)
                .map_err(nm_error_to_nmstate)?;
        }
    }
    Ok(())
}
