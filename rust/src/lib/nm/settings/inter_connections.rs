// SPDX-License-Identifier: Apache-2.0

use std::collections::{hash_map::Entry, HashMap};
use std::str::FromStr;

use super::{
    super::nm_dbus::{
        NmActiveConnection, NmConnection, NmSettingsConnectionFlag,
    },
    connection::{
        is_nm_iface_type_userspace, NM_SETTING_INFINIBAND_SETTING_NAME,
    },
    ovs::get_ovs_port_name,
};

use crate::{
    ErrorKind, Interface, InterfaceType, MergedInterfaces, NmstateError,
};

const NM_UUID_LEN: usize = 36;

pub(crate) fn use_uuid_for_controller_reference(
    nm_conns: &mut [NmConnection],
    merged_ifaces: &MergedInterfaces,
    exist_nm_conns: &[NmConnection],
    nm_acs: &[NmActiveConnection],
) -> Result<(), NmstateError> {
    let mut name_type_2_uuid_index: HashMap<(String, String), String> =
        HashMap::new();

    for nm_conn in nm_conns.iter() {
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

    for nm_ac in nm_acs {
        match name_type_2_uuid_index
            .entry((nm_ac.iface_name.to_string(), nm_ac.iface_type.to_string()))
        {
            // Prefer newly created NmConnection
            Entry::Occupied(_) => {
                continue;
            }
            Entry::Vacant(v) => {
                v.insert(nm_ac.uuid.to_string());
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
                    // Prefer newly created NmConnection or activated one over
                    // existing one
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
            if let Some(merged_iface) = merged_ifaces
                .user_ifaces
                .get(&(ctrl_name.to_string(), InterfaceType::OvsBridge))
            {
                if let Interface::OvsBridge(ovs_br_iface) = &merged_iface.merged
                {
                    if let Some(iface_name) = nm_conn.iface_name() {
                        if let Some(ovs_port_name) =
                            get_ovs_port_name(ovs_br_iface, iface_name)
                        {
                            ctrl_name = ovs_port_name.to_string();
                        } else {
                            // User is attaching port to existing OVS bridge
                            // using `controller` property without OVS bridge
                            // interface mentioned in desire state
                            ctrl_name = iface_name.to_string();
                        }
                    }
                }
            } else {
                let e = NmstateError::new(
                    ErrorKind::Bug,
                    format!(
                        "Failed to find OVS Bridge interface for \
                        NmConnection {nm_conn:?}"
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
                {ctrl_name}, {ctrl_type}"
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
    merged_ifaces: &MergedInterfaces,
    exist_nm_conns: &[NmConnection],
    nm_acs: &[NmActiveConnection],
) {
    // Pending changes: "child_iface_name: parent_nm_uuid"
    let mut pending_changes: HashMap<String, String> = HashMap::new();

    for iface in merged_ifaces
        .kernel_ifaces
        .values()
        .filter(|i| i.is_changed())
    {
        if let Some(parent) = iface.for_apply.as_ref().and_then(|i| i.parent())
        {
            if let Some(parent_uuid) =
                search_uuid_of_kernel_nm_conns(nm_conns, parent)
                    .or_else(|| search_uuid_of_kernel_nm_acs(nm_acs, parent))
                    .or_else(|| {
                        search_uuid_of_kernel_nm_conns(exist_nm_conns, parent)
                    })
            {
                pending_changes.insert(
                    iface.merged.name().to_string(),
                    parent_uuid.to_string(),
                );
            }
        }
    }

    for nm_conn in nm_conns {
        if let (Some(iface_name), Some(nm_iface_type)) =
            (nm_conn.iface_name(), nm_conn.iface_type())
        {
            // InfiniBand parent does not support UUID reference
            if !is_nm_iface_type_userspace(nm_iface_type)
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
                && !is_nm_iface_type_userspace(nm_iface_type)
            {
                return Some(uuid.to_string());
            }
        }
    }
    None
}

fn search_uuid_of_kernel_nm_acs(
    nm_acs: &[NmActiveConnection],
    iface_name: &str,
) -> Option<String> {
    for nm_ac in nm_acs {
        if !is_nm_iface_type_userspace(nm_ac.iface_type.as_str())
            && nm_ac.iface_name.as_str() == iface_name
        {
            return Some(nm_ac.uuid.to_string());
        }
    }
    None
}

// Copy NmConnection with specified UUID and its controllers/parents to
// `nm_conns_to_update`
fn parents_and_controllers_in_memory(
    nm_conns_to_update: &[NmConnection],
    in_memory_nm_conns: &HashMap<String, &NmConnection>,
    name_or_uuid: &str,
    nm_iface_type: Option<&str>,
) -> Vec<NmConnection> {
    let mut ret: Vec<NmConnection> = Vec::new();

    // TODO: Create NmConnectionBank to hold all the search and
    // priority(like prefer activated over other) code in single place
    let nm_conn = if name_or_uuid.len() == NM_UUID_LEN {
        let uuid = name_or_uuid;
        if let Some(c) =
            nm_conns_to_update.iter().find(|c| c.uuid() == Some(uuid))
        {
            c
        } else if let Some(nm_conn) = in_memory_nm_conns.get(uuid) {
            ret.push((*nm_conn).clone());
            nm_conn
        } else {
            return ret;
        }
    } else {
        let name = name_or_uuid;
        if nm_iface_type.is_none() {
            // We should ignore all user space interfaces
            if let Some(c) = nm_conns_to_update.iter().find(|c| {
                c.iface_name() == Some(name)
                    && !is_nm_iface_type_userspace(c.iface_type().unwrap_or(""))
            }) {
                c
            } else if let Some(nm_conn) =
                in_memory_nm_conns.values().find(|c| {
                    c.iface_name() == Some(name)
                        && !is_nm_iface_type_userspace(
                            c.iface_type().unwrap_or(""),
                        )
                })
            {
                ret.push((*nm_conn).clone());
                nm_conn
            } else {
                return ret;
            }
        } else {
            // nm_iface_type defined
            if let Some(c) = nm_conns_to_update.iter().find(|c| {
                c.iface_name() == Some(name) && c.iface_type() == nm_iface_type
            }) {
                c
            } else if let Some(nm_conn) =
                in_memory_nm_conns.values().find(|c| {
                    c.iface_name() == Some(name)
                        && c.iface_type() == nm_iface_type
                })
            {
                ret.push((*nm_conn).clone());
                nm_conn
            } else {
                return ret;
            }
        }
    };

    if let Some(parent) = nm_conn.parent() {
        ret.extend(parents_and_controllers_in_memory(
            nm_conns_to_update,
            in_memory_nm_conns,
            parent,
            None,
        ));
    }
    if let (Some(ctrl), ctrl_type) =
        (nm_conn.controller(), nm_conn.controller_type())
    {
        ret.extend(parents_and_controllers_in_memory(
            nm_conns_to_update,
            in_memory_nm_conns,
            ctrl,
            ctrl_type,
        ));
    }
    ret
}

// Find all NmConnection in memory and not listed in `nm_conns_to_update`
// Only activated NmConnection included.
fn get_in_memory_nm_conns<'a>(
    nm_conns_to_update: &[NmConnection],
    exist_nm_conns: &'a [NmConnection],
    nm_acs: &[NmActiveConnection],
) -> HashMap<String, &'a NmConnection> {
    let mut ret: HashMap<String, &NmConnection> = HashMap::new();
    let nm_ac_uuids: Vec<&str> =
        nm_acs.iter().map(|a| a.uuid.as_str()).collect();
    for nm_conn in exist_nm_conns {
        if nm_conn.flags.contains(&NmSettingsConnectionFlag::Unsaved) {
            if let Some(uuid) = nm_conn.uuid() {
                if nm_ac_uuids.contains(&uuid)
                    && !nm_conns_to_update
                        .iter()
                        .any(|c| c.uuid() == Some(uuid))
                {
                    ret.insert(uuid.to_string(), nm_conn);
                }
            }
        }
    }
    ret
}

pub(crate) fn save_parent_port_and_ctrl_to_disk(
    nm_conns_to_update: &mut Vec<NmConnection>,
    exist_nm_conns: &[NmConnection],
    nm_acs: &[NmActiveConnection],
) {
    let mut pending_changes: HashMap<String, NmConnection> = HashMap::new();

    let in_memory_nm_conns =
        get_in_memory_nm_conns(nm_conns_to_update, exist_nm_conns, nm_acs);

    for nm_conn in nm_conns_to_update
        .as_slice()
        .iter()
        .filter(|c| c.parent().is_some() || c.controller().is_some())
    {
        if let Some(uuid) = nm_conn.uuid() {
            for new_nm_conn in parents_and_controllers_in_memory(
                nm_conns_to_update.as_slice(),
                &in_memory_nm_conns,
                uuid,
                None,
            ) {
                if let Some(new_conn_uuid) = new_nm_conn.uuid() {
                    pending_changes
                        .insert(new_conn_uuid.to_string(), new_nm_conn);
                }
            }
        }
    }

    // The ports of controllers should also be persistent so the controller
    // is not partially configured.

    // We need to run this loop twice, because ovs-iface might refer to
    // ovs-port which is not added into pending_changes yet.
    for _ in 0..2 {
        for (uuid, nm_conn) in in_memory_nm_conns.iter() {
            if !pending_changes.contains_key(uuid.as_str()) {
                if let (Some(ctrl), ctrl_type) =
                    (nm_conn.controller(), nm_conn.controller_type())
                {
                    // Check if this in-memory connection is refer to
                    // anyone in `nm_conns_to_update`
                    if ctrl.len() == NM_UUID_LEN {
                        if pending_changes.contains_key(ctrl) {
                            pending_changes
                                .insert(uuid.to_string(), (*nm_conn).clone());
                        }
                    } else if pending_changes.values().any(|c| {
                        c.iface_name() == Some(ctrl)
                            && c.iface_type() == ctrl_type
                    }) {
                        pending_changes
                            .insert(uuid.to_string(), (*nm_conn).clone());
                    }
                }
            }
        }
    }

    for (uuid, nm_conn) in pending_changes.drain() {
        log::info!(
            "Persistent NM connection {uuid} id {:?} name {:?} type {:?} \
            because its parent, port or controller of other persistent \
            desired interface",
            nm_conn.id(),
            nm_conn.iface_name(),
            nm_conn.iface_type()
        );
        if !nm_conns_to_update
            .as_slice()
            .iter()
            .any(|c| c.uuid() == Some(&uuid))
        {
            nm_conns_to_update.push(nm_conn);
        }
    }
}
