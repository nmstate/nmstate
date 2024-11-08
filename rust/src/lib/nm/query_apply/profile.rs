// SPDX-License-Identifier: Apache-2.0

use std::collections::{hash_map::Entry, HashMap};

use super::super::nm_dbus::{
    self, NmApi, NmConnection, NmIfaceType, NmSettingsConnectionFlag,
};
use super::super::{error::nm_error_to_nmstate, profile::NmProfile};

use crate::{ErrorKind, NmstateError};

const ACTIVATION_RETRY_COUNT: usize = 6;
const ACTIVATION_RETRY_INTERVAL: u64 = 1;

impl NmProfile {
    pub(crate) fn is_up(&self) -> bool {
        self.merged_iface.for_apply.as_ref().map(|i| i.is_up()) == Some(true)
    }

    pub(crate) fn is_down(&self) -> bool {
        self.merged_iface.for_apply.as_ref().map(|i| i.is_down()) == Some(true)
    }
}

pub(crate) fn delete_exist_profiles(
    nm_api: &mut NmApi,
    exist_nm_conns: &[NmConnection],
    nm_profiles: &[NmProfile],
) -> Result<(), NmstateError> {
    let excluded_uuids: Vec<&str> =
        nm_profiles.iter().filter_map(|p| p.conn.uuid()).collect();
    // Array of <interface_name, NM interface type, MAC address>
    let mut changed_ifaces: Vec<(&str, &NmIfaceType, Option<&str>)> =
        Vec::new();
    let mut uuids_to_delete: Vec<&str> = Vec::new();

    for nm_profile in nm_profiles {
        let nm_conn = &nm_profile.conn;
        if let Some(nm_iface_type) = nm_profile.conn.iface_type() {
            if nm_iface_type == &NmIfaceType::Vpn {
                // For VPN, the we use connection id instead of interface name
                // to search existing NM connections
                if let Some(name) = nm_conn.id() {
                    changed_ifaces.push((name, nm_iface_type, None));
                }
            } else {
                changed_ifaces.push((
                    nm_profile.merged_iface.merged.name(),
                    nm_iface_type,
                    nm_profile
                        .merged_iface
                        .merged
                        .base_iface()
                        .mac_address
                        .as_deref(),
                ));
            }
        }
    }
    for exist_nm_conn in exist_nm_conns {
        let uuid = if let Some(u) = exist_nm_conn.uuid() {
            u
        } else {
            continue;
        };

        if excluded_uuids.contains(&uuid) {
            continue;
        }

        // Volatile nm_conn will be automatically removed once deactivated.
        // Hence no need to deactivate.
        if exist_nm_conn
            .flags
            .contains(&NmSettingsConnectionFlag::Volatile)
        {
            continue;
        }

        for (iface_name, nm_iface_type, mac) in changed_ifaces.as_slice() {
            if is_nm_conn_match(exist_nm_conn, iface_name, nm_iface_type, *mac)
            {
                log::info!(
                    "Deleting existing duplicate connection \
                    UUID {}, id {:?} type {:?} name {:?}",
                    uuid,
                    exist_nm_conn.id(),
                    exist_nm_conn.iface_type(),
                    exist_nm_conn.iface_name(),
                );
                uuids_to_delete.push(uuid);
            }
        }
    }
    delete_profiles(nm_api, &uuids_to_delete)
}

pub(crate) fn save_nm_profiles<'a, T>(
    nm_api: &mut NmApi,
    nm_conns: T,
    memory_only: bool,
) -> Result<(), NmstateError>
where
    T: Iterator<Item = &'a NmConnection>,
{
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

pub(crate) async fn activate_nm_profiles<'a, T>(
    nm_api: &mut NmApi<'_>,
    nm_profiles: T,
) -> Result<(), NmstateError>
where
    T: Iterator<Item = &'a NmProfile>,
{
    let mut nm_profiles: Vec<&NmProfile> = nm_profiles.collect();

    let nm_acs = nm_api
        .active_connections_get()
        .map_err(nm_error_to_nmstate)?;
    let nm_ac_uuids: Vec<&str> =
        nm_acs.iter().map(|nm_ac| &nm_ac.uuid as &str).collect();

    for i in 1..ACTIVATION_RETRY_COUNT + 1 {
        if !nm_profiles.is_empty() {
            let remain_nm_profiles = _activate_nm_profiles(
                nm_api,
                nm_profiles.as_slice(),
                nm_ac_uuids.as_slice(),
                i,
            )?;
            if remain_nm_profiles.is_empty() {
                break;
            }
            if i == ACTIVATION_RETRY_COUNT {
                return Err(remain_nm_profiles[0].1.clone());
            }
            nm_profiles.clear();
            for (remain_nm_profile, e) in remain_nm_profiles {
                log::info!("Got activation failure {e}");
                nm_profiles.push(remain_nm_profile);
            }
            let wait_internal = ACTIVATION_RETRY_INTERVAL * (1 << i);
            log::info!("Will retry activation {wait_internal} seconds");
            for _ in 0..wait_internal {
                nm_api
                    .extend_timeout_if_required()
                    .map_err(nm_error_to_nmstate)?;
                tokio::time::sleep(std::time::Duration::from_secs(1)).await;
            }
        } else {
            break;
        }
    }
    Ok(())
}

// Return list of activation failed `NmConnection` which we can retry
fn _activate_nm_profiles<'a>(
    nm_api: &mut NmApi,
    nm_profiles: &[&'a NmProfile],
    nm_ac_uuids: &[&str],
    retry_count: usize,
) -> Result<Vec<(&'a NmProfile, NmstateError)>, NmstateError> {
    let mut failed_nm_profiles: Vec<(&NmProfile, NmstateError)> = Vec::new();
    for nm_profile in nm_profiles
        .iter()
        .filter(|p| p.merged_iface.merged.is_controller())
    {
        if retry_count == 1 && nm_profile.skip_first_activation {
            continue;
        }
        let nm_conn = &nm_profile.conn;
        if let Some(uuid) = nm_conn.uuid() {
            if nm_ac_uuids.contains(&uuid) {
                if let Err(e) = reapply_or_activate(nm_api, nm_profile) {
                    if e.kind().can_retry() {
                        failed_nm_profiles.push((nm_profile, e));
                    } else {
                        return Err(e);
                    }
                }
            } else if let Err(e) = nm_api
                .connection_activate(uuid)
                .map_err(nm_error_to_nmstate)
            {
                if e.kind().can_retry() {
                    failed_nm_profiles.push((nm_profile, e));
                } else {
                    return Err(e);
                }
            }
        }
    }
    for nm_profile in nm_profiles
        .iter()
        .filter(|p| !p.merged_iface.merged.is_controller())
    {
        let nm_conn = &nm_profile.conn;
        if let Some(uuid) = nm_conn.uuid() {
            if nm_ac_uuids.contains(&uuid) {
                log::info!(
                    "Reapplying connection {}: {}/{}",
                    uuid,
                    nm_profile.merged_iface.merged.name(),
                    nm_profile.merged_iface.merged.iface_type(),
                );
                if let Err(e) = reapply_or_activate(nm_api, nm_profile) {
                    if e.kind().can_retry() {
                        failed_nm_profiles.push((nm_profile, e));
                    } else {
                        return Err(e);
                    }
                }
            } else {
                log::info!(
                    "Activating connection {}: {}/{}",
                    uuid,
                    nm_profile.merged_iface.merged.name(),
                    nm_profile.merged_iface.merged.iface_type(),
                );
                if let Err(e) = nm_api
                    .connection_activate(uuid)
                    .map_err(nm_error_to_nmstate)
                {
                    if e.kind().can_retry() {
                        failed_nm_profiles.push((nm_profile, e));
                    } else {
                        return Err(e);
                    }
                }
            }
        }
    }
    Ok(failed_nm_profiles)
}

pub(crate) fn deactivate_nm_profiles<'a, T>(
    nm_api: &mut NmApi,
    nm_conns: T,
) -> Result<(), NmstateError>
where
    T: Iterator<Item = &'a NmConnection>,
{
    for nm_conn in nm_conns {
        if let Some(uuid) = nm_conn.uuid() {
            log::info!(
                "Deactivating connection {}: {}/{}",
                uuid,
                nm_conn.iface_name().unwrap_or(""),
                nm_conn.iface_type().cloned().unwrap_or_default()
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
) -> HashMap<(&str, NmIfaceType), Vec<&NmConnection>> {
    let mut ret: HashMap<(&str, NmIfaceType), Vec<&NmConnection>> =
        HashMap::new();
    for nm_conn in nm_conns {
        if let Some(iface_name) = nm_conn.iface_name() {
            if let Some(nm_iface_type) = nm_conn.iface_type() {
                if nm_iface_type == &NmIfaceType::Veth {
                    match ret.entry((iface_name, NmIfaceType::Ethernet)) {
                        Entry::Occupied(o) => {
                            o.into_mut().push(nm_conn);
                        }
                        Entry::Vacant(v) => {
                            v.insert(vec![nm_conn]);
                        }
                    };
                }
                if nm_iface_type == &NmIfaceType::Ethernet {
                    match ret.entry((iface_name, NmIfaceType::Veth)) {
                        Entry::Occupied(o) => {
                            o.into_mut().push(nm_conn);
                        }
                        Entry::Vacant(v) => {
                            v.insert(vec![nm_conn]);
                        }
                    };
                }
                match ret.entry((iface_name, nm_iface_type.clone())) {
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
    nm_profile: &NmProfile,
) -> Result<(), NmstateError> {
    let nm_conn = &nm_profile.conn;
    let uuid = match nm_conn.uuid() {
        Some(u) => u,
        None => {
            return Err(NmstateError::new(
                ErrorKind::Bug,
                format!(
                    "reapply_or_activate(): Got NmConnection without UUID \
                    {nm_conn:?}"
                ),
            ));
        }
    };
    if let Err(e) = nm_api.connection_reapply(
        nm_profile.merged_iface.merged.name(),
        &nm_conn.iface_type().cloned().unwrap_or_default(),
        nm_conn,
    ) {
        log::info!(
            "Reapply operation failed on {} {} {uuid}, \
            reason: {}, retry on normal activation",
            nm_profile.merged_iface.merged.name(),
            nm_profile.merged_iface.merged.iface_type(),
            e
        );
        log::info!(
            "Activating connection {}: {}/{}",
            uuid,
            nm_profile.merged_iface.merged.name(),
            nm_profile.merged_iface.merged.iface_type(),
        );
        nm_api
            .connection_activate(uuid)
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}

pub(crate) fn is_uuid(value: &str) -> bool {
    uuid::Uuid::parse_str(value).is_ok()
}

fn is_nm_conn_match(
    nm_conn: &NmConnection,
    iface_name: &str,
    nm_iface_type: &NmIfaceType,
    mac: Option<&str>,
) -> bool {
    if Some(nm_iface_type) != nm_conn.iface_type() {
        return false;
    }

    if let Some(cur_iface_name) = nm_conn.iface_name() {
        if cur_iface_name != iface_name {
            return false;
        }
    } else {
        if mac.is_none() {
            return false;
        }
        // Check whether nm_conn is using MAC address matching
        if mac
            != nm_conn
                .wired
                .as_ref()
                .and_then(|w| w.mac_address.as_deref())
        {
            return false;
        }
    }

    true
}
