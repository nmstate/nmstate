use std::collections::{hash_map::Entry, HashMap};

use log::{error, info};
use nm_dbus::{NmApi, NmConnection};

use crate::{
    nm::checkpoint::nm_checkpoint_timeout_extend,
    nm::connection::{
        iface_type_to_nm, NM_SETTING_VETH_SETTING_NAME,
        NM_SETTING_WIRED_SETTING_NAME,
    },
    nm::error::nm_error_to_nmstate,
    nm::ovs::get_ovs_port_name,
    ErrorKind, Interface, InterfaceType, NmstateError,
};

// We only adjust timeout for every 20 profile additions.
const TIMEOUT_ADJUST_PROFILE_GROUP_SIZE: usize = 20;
const TIMEOUT_SECONDS_FOR_PROFILE_ADDTION: u32 = 60;
const TIMEOUT_SECONDS_FOR_PROFILE_ACTIVATION: u32 = 60;
const TIMEOUT_SECONDS_FOR_PROFILE_DEACTIVATION: u32 = 60;

// Found existing profile, prefer the activated one
pub(crate) fn get_exist_profile<'a>(
    exist_nm_conns: &'a [NmConnection],
    iface_name: &str,
    iface_type: &InterfaceType,
    nm_ac_uuids: &[&str],
) -> Option<&'a NmConnection> {
    let mut found_nm_conns: Vec<&NmConnection> = Vec::new();
    for exist_nm_conn in exist_nm_conns {
        let nm_iface_type = if let Ok(t) = iface_type_to_nm(iface_type) {
            // The iface_type will never be veth as top level code
            // `pre_edit_clean()` has confirmed so.
            t
        } else {
            continue;
        };
        if exist_nm_conn.iface_name() == Some(iface_name)
            && (exist_nm_conn.iface_type() == Some(&nm_iface_type)
                || (nm_iface_type == NM_SETTING_WIRED_SETTING_NAME
                    && exist_nm_conn.iface_type()
                        == Some(NM_SETTING_VETH_SETTING_NAME)))
        {
            if let Some(uuid) = exist_nm_conn.uuid() {
                // Prefer activated connection
                if nm_ac_uuids.contains(&uuid) {
                    return Some(exist_nm_conn);
                }
            }
            found_nm_conns.push(exist_nm_conn);
        }
    }
    found_nm_conns.pop()
}

pub(crate) fn delete_exist_profiles(
    nm_api: &NmApi,
    exist_nm_conns: &[NmConnection],
    nm_conns: &[NmConnection],
) -> Result<(), NmstateError> {
    let mut excluded_uuids: Vec<&str> = Vec::new();
    let mut changed_iface_name_types: Vec<(&str, &str)> = Vec::new();
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
        if !excluded_uuids.contains(&uuid)
            && changed_iface_name_types.contains(&(iface_name, nm_iface_type))
        {
            info!("Deleting existing connection {:?}", exist_nm_conn);
            nm_api
                .connection_delete(uuid)
                .map_err(nm_error_to_nmstate)?;
        }
    }
    Ok(())
}

pub(crate) fn save_nm_profiles(
    nm_api: &nm_dbus::NmApi,
    nm_conns: &[NmConnection],
    checkpoint: &str,
) -> Result<(), NmstateError> {
    for (index, nm_conn) in nm_conns.iter().enumerate() {
        // Only extend the timeout every
        // TIMEOUT_ADJUST_PROFILE_ADDTION_GROUP_SIZE profile addition.
        if index % TIMEOUT_ADJUST_PROFILE_GROUP_SIZE
            == TIMEOUT_ADJUST_PROFILE_GROUP_SIZE - 1
        {
            nm_checkpoint_timeout_extend(
                checkpoint,
                TIMEOUT_SECONDS_FOR_PROFILE_ADDTION,
            )?;
        }
        info!("Creating/Modifying connection {:?}", nm_conn);
        nm_api
            .connection_add(nm_conn)
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}

pub(crate) fn activate_nm_profiles(
    nm_api: &nm_dbus::NmApi,
    nm_conns: &[NmConnection],
    checkpoint: &str,
) -> Result<(), NmstateError> {
    for nm_conn in nm_conns {
        nm_checkpoint_timeout_extend(
            checkpoint,
            TIMEOUT_SECONDS_FOR_PROFILE_ACTIVATION,
        )?;
        if let Some(uuid) = nm_conn.uuid() {
            info!(
                "Activating connection {}: {}/{}",
                uuid,
                nm_conn.iface_name().unwrap_or(""),
                nm_conn.iface_type().unwrap_or("")
            );
            if let Err(e) = nm_api.connection_reapply(nm_conn) {
                info!(
                    "Reapply operation failed trying activation, reason: {}, \
                    retry on normal activation",
                    e
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
    nm_api: &nm_dbus::NmApi,
    nm_conns: &[&NmConnection],
    checkpoint: &str,
) -> Result<(), NmstateError> {
    for (index, nm_conn) in nm_conns.iter().enumerate() {
        if (index + 1) % TIMEOUT_ADJUST_PROFILE_GROUP_SIZE == 0 {
            nm_checkpoint_timeout_extend(
                checkpoint,
                TIMEOUT_SECONDS_FOR_PROFILE_DEACTIVATION,
            )?;
        }
        if let Some(uuid) = nm_conn.uuid() {
            info!(
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

pub(crate) fn use_uuid_for_controller_reference(
    nm_conns: &mut [NmConnection],
    des_user_space_ifaces: &HashMap<(String, InterfaceType), Interface>,
    cur_user_space_ifaces: &HashMap<(String, InterfaceType), Interface>,
    exist_nm_conns: &[NmConnection],
) -> Result<(), NmstateError> {
    let mut name_type_2_uuid_index: HashMap<(String, String), String> =
        HashMap::new();

    // This block does not need nm_conn to be mutable, using iter_mut()
    // just to suppress the rust clippy warning message
    for nm_conn in nm_conns.iter_mut() {
        let iface_type = if let Some(i) = nm_conn.iface_type() {
            i
        } else {
            continue;
        };
        if let Some(uuid) = nm_conn.uuid() {
            if let Some(iface_name) = nm_conn.iface_name() {
                name_type_2_uuid_index.insert(
                    (iface_name.to_string(), iface_type.to_string()),
                    uuid.to_string(),
                );
            }
        }
    }

    for nm_conn in exist_nm_conns {
        let iface_type = if let Some(i) = nm_conn.iface_type() {
            i
        } else {
            continue;
        };
        if let Some(uuid) = nm_conn.uuid() {
            if let Some(iface_name) = nm_conn.iface_name() {
                match name_type_2_uuid_index
                    .entry((iface_name.to_string(), iface_type.to_string()))
                {
                    // Prefer newly created NmConnection over existing one
                    Entry::Occupied(_) => {
                        continue;
                    }
                    Entry::Vacant(v) => {
                        v.insert(uuid.to_string());
                    }
                }
            }
        }
    }

    let mut pending_changes: Vec<(&mut NmConnection, String)> = Vec::new();

    for nm_conn in nm_conns.iter_mut() {
        let ctrl_type = if let Some(t) = nm_conn.controller_type() {
            t
        } else {
            continue;
        };
        let mut ctrl_name = if let Some(n) = nm_conn.controller() {
            n.to_string()
        } else {
            continue;
        };

        if ctrl_type == "ovs-port" {
            if let Some(Interface::OvsBridge(ovs_br_iface)) =
                des_user_space_ifaces
                    .get(&(ctrl_name.to_string(), InterfaceType::OvsBridge))
                    .or_else(|| {
                        cur_user_space_ifaces.get(&(
                            ctrl_name.to_string(),
                            InterfaceType::OvsBridge,
                        ))
                    })
            {
                if let Some(iface_name) = nm_conn.iface_name() {
                    if let Some(ovs_port_name) =
                        get_ovs_port_name(ovs_br_iface, iface_name)
                    {
                        ctrl_name = ovs_port_name.to_string();
                    } else {
                        let e = NmstateError::new(
                            ErrorKind::Bug,
                            format!(
                                "Failed to find OVS port name for \
                                NmConnection {:?}",
                                nm_conn
                            ),
                        );
                        error!("{}", e);
                        return Err(e);
                    }
                }
            } else {
                let e = NmstateError::new(
                    ErrorKind::Bug,
                    format!(
                        "Failed to find OVS Bridge interface for \
                        NmConnection {:?}",
                        nm_conn
                    ),
                );
                error!("{}", e);
                return Err(e);
            }
        }

        if let Some(uuid) = name_type_2_uuid_index
            .get(&(ctrl_name.clone(), ctrl_type.to_string()))
        {
            pending_changes.push((nm_conn, uuid.to_string()));
        } else {
            let e = NmstateError::new(
                ErrorKind::Bug,
                format!(
                    "BUG: Failed to find UUID of controller connection: \
                {}, {}",
                    ctrl_name, ctrl_type
                ),
            );
            error!("{}", e);
            return Err(e);
        }
    }
    for (nm_conn, uuid) in pending_changes {
        if let Some(ref mut nm_conn_set) = &mut nm_conn.connection {
            nm_conn_set.controller = Some(uuid.to_string());
        }
    }
    Ok(())
}
