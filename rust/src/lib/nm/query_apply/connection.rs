// SPDX-License-Identifier: Apache-2.0

use super::super::{
    NmConnectionMatcher,
    error::nm_error_to_nmstate,
    nm_dbus::{
        self, NmActiveConnection, NmApi, NmConnection, NmIfaceType,
        NmSettingsConnectionFlag,
    },
};
use crate::{ErrorKind, MergedNetworkState, NmstateError};

const ACTIVATION_RETRY_COUNT: usize = 6;
const ACTIVATION_RETRY_INTERVAL: u64 = 1;

pub(crate) async fn delete_exist_connections(
    nm_api: &mut NmApi<'_>,
    merged_state: &MergedNetworkState,
    conn_matcher: &NmConnectionMatcher,
    nm_conns_to_store: &[NmConnection],
) -> Result<(), NmstateError> {
    let excluded_uuids: Vec<&str> =
        nm_conns_to_store.iter().filter_map(|c| c.uuid()).collect();
    let mut uuids_to_delete: Vec<&str> = Vec::new();

    for merged_iface in
        merged_state.interfaces.iter().filter(|i| i.is_changed())
    {
        for saved_nm_conn in conn_matcher
            .get_saved(merged_iface.merged.base_iface())
            .into_iter()
            .filter(|nm_conn| {
                !nm_conn.flags.contains(&NmSettingsConnectionFlag::Volatile)
            })
        {
            if let Some(uuid) = saved_nm_conn.uuid()
                && !excluded_uuids.contains(&uuid)
            {
                uuids_to_delete.push(uuid);
                log::info!(
                    "Deleting existing duplicate connection {uuid}: {}/{}",
                    merged_iface.merged.name(),
                    merged_iface.merged.iface_type(),
                );
            }
        }
    }
    delete_connections(nm_api, &uuids_to_delete).await
}

pub(crate) async fn save_nm_connections(
    nm_api: &mut NmApi<'_>,
    nm_conns: &[NmConnection],
    memory_only: bool,
) -> Result<(), NmstateError> {
    for nm_conn in nm_conns {
        let uuid = nm_conn.uuid().unwrap_or_default();
        let nm_iface_type = nm_conn.iface_type().cloned().unwrap_or_default();
        // For MAC identifier interface, it does not have interface name
        // in NM connection, print connection id instead.
        let iface_name = nm_conn
            .iface_name()
            .or_else(|| nm_conn.id())
            .unwrap_or("undefined");
        if nm_conn.obj_path.is_empty() {
            log::info!(
                "Creating connection {uuid}: {iface_name}/{nm_iface_type}"
            );
        } else {
            log::info!(
                "Modifying connection {uuid}: {iface_name}/{nm_iface_type}"
            );
        }
        nm_api
            .connection_add(nm_conn, memory_only)
            .await
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}

pub(crate) async fn activate_nm_connections(
    nm_api: &mut NmApi<'_>,
    nm_conns: &[NmConnection],
    conn_matcher: &NmConnectionMatcher,
) -> Result<(), NmstateError> {
    let mut nm_conns = nm_conns.to_vec();
    for i in 1..ACTIVATION_RETRY_COUNT + 1 {
        if !nm_conns.is_empty() {
            let remain_nm_conns = _activate_nm_connections(
                nm_api,
                nm_conns.as_slice(),
                conn_matcher,
            )
            .await?;
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
                    .await
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
async fn _activate_nm_connections(
    nm_api: &mut NmApi<'_>,
    nm_conns: &[NmConnection],
    conn_matcher: &NmConnectionMatcher,
) -> Result<Vec<(NmConnection, NmstateError)>, NmstateError> {
    // Contain a list of `(iface_name, nm_iface_type)`.
    let mut new_controllers: Vec<(&str, NmIfaceType)> = Vec::new();
    let mut failed_nm_conns: Vec<(NmConnection, NmstateError)> = Vec::new();
    for nm_conn in nm_conns
        .iter()
        .filter(|c| c.iface_type().map(|t| t.is_controller()) == Some(true))
    {
        if let Some(uuid) = nm_conn.uuid() {
            if let Some(nm_ac) = conn_matcher.get_nm_ac_by_uuid(uuid) {
                if let Err(e) =
                    reapply_or_activate(nm_api, nm_conn, nm_ac).await
                {
                    if e.kind().can_retry() {
                        failed_nm_conns.push((nm_conn.clone(), e));
                    } else {
                        return Err(e);
                    }
                }
            } else {
                new_controllers.push((
                    nm_conn.iface_name().unwrap_or(""),
                    nm_conn.iface_type().cloned().unwrap_or_default(),
                ));
                log::info!(
                    "Activating connection {}: {}/{}",
                    uuid,
                    nm_conn.iface_name().unwrap_or(""),
                    nm_conn.iface_type().cloned().unwrap_or_default()
                );
                if let Err(e) = nm_api
                    .connection_activate(uuid)
                    .await
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
    for nm_conn in nm_conns
        .iter()
        .filter(|c| c.iface_type().map(|t| t.is_controller()) != Some(true))
    {
        if let Some(uuid) = nm_conn.uuid() {
            if let Some(nm_ac) = conn_matcher.get_nm_ac_by_uuid(uuid) {
                if let Err(e) =
                    reapply_or_activate(nm_api, nm_conn, nm_ac).await
                {
                    if e.kind().can_retry() {
                        failed_nm_conns.push((nm_conn.clone(), e));
                    } else {
                        return Err(e);
                    }
                }
            } else {
                if let (Some(ctrller), Some(ctrller_type)) =
                    (nm_conn.controller(), nm_conn.controller_type())
                    && nm_conn.iface_type() != Some(&NmIfaceType::OvsIface)
                {
                    // OVS port does not do auto port activation.
                    if new_controllers.contains(&(ctrller, *ctrller_type))
                        && ctrller_type != &NmIfaceType::OvsPort
                    {
                        log::info!(
                            "Skip connection activation as its controller \
                             already activated its ports: {}: {}/{}",
                            uuid,
                            nm_conn.iface_name().unwrap_or(""),
                            nm_conn.iface_type().cloned().unwrap_or_default()
                        );
                        continue;
                    }
                }
                log::info!(
                    "Activating connection {}: {}/{}",
                    uuid,
                    nm_conn.iface_name().unwrap_or(""),
                    nm_conn.iface_type().cloned().unwrap_or_default()
                );
                if let Err(e) = nm_api
                    .connection_activate(uuid)
                    .await
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

pub(crate) async fn deactivate_nm_connections(
    nm_api: &mut NmApi<'_>,
    nm_conns: &[NmConnection],
) -> Result<(), NmstateError> {
    for nm_conn in nm_conns {
        if let Some(uuid) = nm_conn.uuid() {
            log::info!(
                "Deactivating connection {}: {}/{}",
                uuid,
                nm_conn.iface_name().unwrap_or(""),
                nm_conn.iface_type().cloned().unwrap_or_default()
            );
            if let Err(e) = nm_api.connection_deactivate(uuid).await
                && e.kind
                    != nm_dbus::ErrorKind::Manager(
                        nm_dbus::NmManagerError::ConnectionNotActive,
                    )
            {
                return Err(nm_error_to_nmstate(e));
            }
        }
    }
    Ok(())
}

pub(crate) async fn delete_connections(
    nm_api: &mut NmApi<'_>,
    uuids: &[&str],
) -> Result<(), NmstateError> {
    for uuid in uuids {
        nm_api
            .connection_delete(uuid)
            .await
            .map_err(nm_error_to_nmstate)?;
    }
    Ok(())
}

async fn reapply_or_activate(
    nm_api: &mut NmApi<'_>,
    nm_conn: &NmConnection,
    nm_ac: &NmActiveConnection,
) -> Result<(), NmstateError> {
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
    if let Some(nm_dev_obj_path) = nm_ac.dev_obj_path.as_deref() {
        log::info!(
            "Reapplying connection {}: {}/{}",
            uuid,
            nm_ac.iface_name,
            nm_ac.iface_type,
        );
        if let Err(e) =
            nm_api.connection_reapply(nm_conn, nm_dev_obj_path).await
        {
            log::info!(
                "Reapply operation failed on {} {} {uuid}, reason: {}, retry \
                 on normal activation",
                nm_ac.iface_name,
                nm_ac.iface_type,
                e
            );
            nm_api
                .connection_activate(uuid)
                .await
                .map_err(nm_error_to_nmstate)?;
        }
    } else {
        nm_api
            .connection_activate(uuid)
            .await
            .map_err(nm_error_to_nmstate)?;
    }

    Ok(())
}
