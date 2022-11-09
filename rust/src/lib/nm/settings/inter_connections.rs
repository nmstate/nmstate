// SPDX-License-Identifier: Apache-2.0

use std::collections::{hash_map::Entry, HashMap};
use std::str::FromStr;

use super::{
    super::nm_dbus::NmConnection,
    connection::{NM_SETTING_INFINIBAND_SETTING_NAME, NM_SETTING_USER_SPACES},
    ovs::get_ovs_port_name,
};

use crate::{ErrorKind, Interface, InterfaceType, NmstateError};

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

        // Skip if its controller is already a UUID
        if uuid::Uuid::from_str(ctrl_name.as_str()).is_ok() {
            continue;
        }

        if ctrl_type == "ovs-port" {
            let cur_ovs_br_iface = cur_user_space_ifaces
                .get(&(ctrl_name.to_string(), InterfaceType::OvsBridge));
            if let Some(Interface::OvsBridge(ovs_br_iface)) =
                des_user_space_ifaces
                    .get(&(ctrl_name.to_string(), InterfaceType::OvsBridge))
                    .or(cur_ovs_br_iface)
            {
                if let Some(iface_name) = nm_conn.iface_name() {
                    if let Some(ovs_port_name) = get_ovs_port_name(
                        ovs_br_iface,
                        iface_name,
                        cur_ovs_br_iface,
                    ) {
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
                        log::error!("{}", e);
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
                log::error!("{}", e);
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
            log::error!("{}", e);
            return Err(e);
        }
    }
    for (nm_conn, uuid) in pending_changes {
        if let Some(nm_conn_set) = &mut nm_conn.connection {
            nm_conn_set.controller = Some(uuid.to_string());
        }
    }
    Ok(())
}

pub(crate) fn use_uuid_for_parent_reference(
    nm_conns: &mut [NmConnection],
    des_kernel_ifaces: &HashMap<String, Interface>,
    exist_nm_conns: &[NmConnection],
) {
    // Pending changes: "child_iface_name: parent_nm_uuid"
    let mut pending_changes: HashMap<String, String> = HashMap::new();

    for iface in des_kernel_ifaces.values() {
        if let Some(parent) = iface.parent() {
            if let Some(parent_uuid) =
                search_uuid_of_kernel_nm_conns(nm_conns, parent).or_else(|| {
                    search_uuid_of_kernel_nm_conns(exist_nm_conns, parent)
                })
            {
                pending_changes
                    .insert(iface.name().to_string(), parent_uuid.to_string());
            }
        }
    }

    for nm_conn in nm_conns {
        if let (Some(iface_name), Some(nm_iface_type)) =
            (nm_conn.iface_name(), nm_conn.iface_type())
        {
            // InfiniBand parent does not support UUID reference
            if !NM_SETTING_USER_SPACES.contains(&nm_iface_type)
                && nm_iface_type != NM_SETTING_INFINIBAND_SETTING_NAME
            {
                if let Some(parent_uuid) = pending_changes.get(iface_name) {
                    nm_conn.set_parent(parent_uuid);
                }
            }
        }
    }
}

fn search_uuid_of_kernel_nm_conns(
    nm_conns: &[NmConnection],
    iface_name: &str,
) -> Option<String> {
    for nm_conn in nm_conns {
        if let (Some(cur_iface_name), Some(nm_iface_type), Some(uuid)) =
            (nm_conn.iface_name(), nm_conn.iface_type(), nm_conn.uuid())
        {
            if cur_iface_name == iface_name
                && !NM_SETTING_USER_SPACES.contains(&nm_iface_type)
            {
                return Some(uuid.to_string());
            }
        }
    }
    None
}
