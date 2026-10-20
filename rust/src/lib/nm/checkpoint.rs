// SPDX-License-Identifier: Apache-2.0

use std::time::{Duration, Instant};

use log::warn;

use crate::{
    ErrorKind, NmstateError,
    nm::{
        error::nm_error_to_nmstate,
        nm_dbus::{NmActiveConnection, NmApi, NmDevice, NmDeviceState},
    },
};

pub(crate) async fn nm_checkpoint_owner() -> Result<String, NmstateError> {
    let connection = zbus::Connection::system().await.map_err(|e| {
        NmstateError::new(ErrorKind::PluginFailure, e.to_string())
    })?;
    let proxy = zbus::fdo::DBusProxy::new(&connection).await.map_err(|e| {
        NmstateError::new(ErrorKind::PluginFailure, e.to_string())
    })?;
    proxy
        .get_name_owner("org.freedesktop.NetworkManager".try_into().map_err(
            |e: zbus::names::Error| {
                NmstateError::new(ErrorKind::Bug, e.to_string())
            },
        )?)
        .await
        .map(|owner| owner.to_string())
        .map_err(|e| NmstateError::new(ErrorKind::PluginFailure, e.to_string()))
}

pub(crate) async fn nm_checkpoint_exists(
    checkpoint: &str,
) -> Result<bool, NmstateError> {
    let nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    nm_api
        .dbus
        .checkpoints()
        .await
        .map(|checkpoints| checkpoints.iter().any(|cp| cp == checkpoint))
        .map_err(nm_error_to_nmstate)
}

pub(crate) async fn nm_checkpoint_timeout_disable(
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    nm_api
        .dbus
        .checkpoint_timeout_extend(checkpoint, 0)
        .await
        .map_err(nm_error_to_nmstate)
}

#[derive(Clone, Debug, Default, serde::Serialize, serde::Deserialize)]
pub(crate) struct RuleCheckpointConnections {
    connections: Vec<(String, String, u32)>,
}

impl RuleCheckpointConnections {
    pub(crate) fn validate_for_checkpoint(&self) -> Result<(), NmstateError> {
        if self
            .connections
            .iter()
            .any(|(_, _, state)| !matches!(state, 1 | 2))
        {
            return Err(NmstateError::new(
                ErrorKind::PluginFailure,
                "Cannot checkpoint external rules while NetworkManager \
                 connections are deactivating or deactivated; retry after \
                 they settle"
                    .into(),
            ));
        }
        Ok(())
    }
}

pub(crate) async fn nm_checkpoint_rule_connections()
-> Result<RuleCheckpointConnections, NmstateError> {
    let mut api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    let connections = api
        .active_connections_get()
        .await
        .map_err(nm_error_to_nmstate)?;
    Ok(RuleCheckpointConnections {
        connections: connections
            .into_iter()
            .map(|c| (c.uuid, c.iface_name, c.state))
            .collect(),
    })
}

pub(crate) async fn nm_checkpoint_rollback_for_rules(
    checkpoint: &str,
    baseline: &RuleCheckpointConnections,
) -> Result<(), NmstateError> {
    let mut api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    let mut rollback_error = None;
    if api
        .dbus
        .checkpoints()
        .await
        .map_err(nm_error_to_nmstate)?
        .iter()
        .any(|cp| cp == checkpoint)
    {
        let owner = nm_checkpoint_owner().await?;
        wait_for_deactivation(&mut api).await?;
        if owner != nm_checkpoint_owner().await? {
            return Err(NmstateError::new(
                ErrorKind::PluginFailure,
                "NetworkManager restarted before checkpoint rollback".into(),
            ));
        }
        let results = api
            .dbus
            .checkpoint_rollback_results(checkpoint)
            .await
            .map_err(nm_error_to_nmstate)?;
        if results.values().any(|status| *status != 0) {
            rollback_error = Some(NmstateError::new(
                ErrorKind::PluginFailure,
                format!(
                    "NetworkManager checkpoint rollback failed: {results:?}"
                ),
            ));
        }
    }
    let started = Instant::now();
    let mut settled_since = None;
    while started.elapsed() < Duration::from_secs(15) {
        let current = nm_checkpoint_rule_connections().await?;
        let devices = api.devices_get().await.map_err(nm_error_to_nmstate)?;
        if connections_settled(baseline, &current, &devices) {
            let settled_since = settled_since.get_or_insert_with(Instant::now);
            if settled_since.elapsed() >= Duration::from_secs(1) {
                return rollback_error.map_or(Ok(()), Err);
            }
        } else {
            settled_since = None;
        }
        tokio::time::sleep(Duration::from_millis(250)).await;
    }
    Err(rollback_error.unwrap_or_else(|| {
        NmstateError::new(
            ErrorKind::PluginFailure,
            "NetworkManager connections did not finish checkpoint rollback"
                .into(),
        )
    }))
}

async fn wait_for_deactivation(
    api: &mut NmApi<'_>,
) -> Result<(), NmstateError> {
    let started = Instant::now();
    let mut quiet_since = None;
    while started.elapsed() < Duration::from_secs(15) {
        let devices = api.devices_get().await.map_err(nm_error_to_nmstate)?;
        let connections = api
            .active_connections_get()
            .await
            .map_err(nm_error_to_nmstate)?;
        // NM can consider a deactivating connection unchanged and skip its
        // reactivation during rollback. Wait until its old active object is
        // gone, including when its profile is already absent from the query.
        if deactivation_finished(&devices, &connections) {
            let quiet_since = quiet_since.get_or_insert_with(Instant::now);
            if quiet_since.elapsed() >= Duration::from_millis(250) {
                return Ok(());
            }
        } else {
            quiet_since = None;
        }
        tokio::time::sleep(Duration::from_millis(250)).await;
    }
    Err(NmstateError::new(
        ErrorKind::PluginFailure,
        "NetworkManager connections are still deactivating; checkpoint \
         rollback will be retried"
            .into(),
    ))
}

fn deactivation_finished(
    devices: &[NmDevice],
    connections: &[NmActiveConnection],
) -> bool {
    devices
        .iter()
        .all(|device| device.state != NmDeviceState::Deactivating)
        && connections
            .iter()
            .all(|connection| !matches!(connection.state, 3 | 4))
}

fn connections_settled(
    baseline: &RuleCheckpointConnections,
    current: &RuleCheckpointConnections,
    devices: &[NmDevice],
) -> bool {
    deactivation_finished(devices, &[])
        && current
            .connections
            .iter()
            .all(|(_, _, state)| matches!(state, 1 | 2))
        && baseline
            .connections
            .iter()
            .filter(|(_, _, state)| *state == 2)
            .all(|(uuid, iface, _)| {
                current.connections.iter().any(
                    |(cur_uuid, cur_iface, cur_state)| {
                        uuid == cur_uuid
                            && iface == cur_iface
                            && *cur_state == 2
                    },
                )
            })
}

// Wait maximum 60 seconds for rollback
pub(crate) const CHECKPOINT_ROLLBACK_TIMEOUT: u32 = 60;

pub(crate) async fn nm_checkpoint_create(
    timeout: u32,
) -> Result<String, NmstateError> {
    let mut nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_create(timeout)
        .await
        .map_err(nm_error_to_nmstate)
}

pub(crate) async fn nm_checkpoint_rollback(
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let mut nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_rollback(checkpoint)
        .await
        .map_err(nm_error_to_nmstate)?;
    if let Err(e) = nm_api
        .wait_checkpoint_rollback(CHECKPOINT_ROLLBACK_TIMEOUT)
        .await
    {
        warn!("{e}");
    }
    Ok(())
}

pub(crate) async fn nm_checkpoint_destroy(
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let mut nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_destroy(checkpoint)
        .await
        .map_err(nm_error_to_nmstate)
}

pub(crate) async fn nm_checkpoint_timeout_extend(
    checkpoint: &str,
    added_time_sec: u32,
) -> Result<(), NmstateError> {
    let nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_timeout_extend(checkpoint, added_time_sec)
        .await
        .map_err(nm_error_to_nmstate)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn checkpoint_rejects_ambiguous_deactivation_baseline() {
        for state in [0, 3, 4] {
            assert!(
                RuleCheckpointConnections {
                    connections: vec![("uuid".into(), "eth1".into(), state)],
                }
                .validate_for_checkpoint()
                .is_err()
            );
        }
        for state in [1, 2] {
            assert!(
                RuleCheckpointConnections {
                    connections: vec![("uuid".into(), "eth1".into(), state)],
                }
                .validate_for_checkpoint()
                .is_ok()
            );
        }
    }

    #[test]
    fn rollback_ignores_unchanged_dhcp_activation() {
        let before = RuleCheckpointConnections {
            connections: vec![("uuid".into(), "eth1".into(), 1)],
        };
        assert!(connections_settled(&before, &before, &[]));
        let current = RuleCheckpointConnections {
            connections: vec![("uuid".into(), "eth1".into(), 2)],
        };
        assert!(connections_settled(&before, &current, &[]));
        assert!(connections_settled(
            &before,
            &RuleCheckpointConnections::default(),
            &[],
        ));
    }

    #[test]
    fn rollback_waits_for_deactivation_before_consuming_checkpoint() {
        let mut device = NmDevice {
            state: NmDeviceState::Deactivating,
            ..Default::default()
        };
        assert!(!deactivation_finished(std::slice::from_ref(&device), &[]));
        device.state = NmDeviceState::Disconnected;
        for state in [3, 4] {
            assert!(!deactivation_finished(
                std::slice::from_ref(&device),
                &[NmActiveConnection {
                    state,
                    ..Default::default()
                }],
            ));
        }
        assert!(deactivation_finished(std::slice::from_ref(&device), &[]));
        for state in [1, 2] {
            assert!(deactivation_finished(
                std::slice::from_ref(&device),
                &[NmActiveConnection {
                    state,
                    ..Default::default()
                }],
            ));
        }
    }

    #[test]
    fn rollback_waits_for_restored_connections() {
        let before = RuleCheckpointConnections {
            connections: vec![("old".into(), "eth1".into(), 2)],
        };
        for current in [
            vec![("old".into(), "eth1".into(), 1)],
            vec![("new".into(), "eth1".into(), 2)],
            vec![("old".into(), "eth2".into(), 2)],
            vec![],
        ] {
            assert!(!connections_settled(
                &before,
                &RuleCheckpointConnections {
                    connections: current
                },
                &[],
            ));
        }
        assert!(connections_settled(&before, &before, &[]));
    }

    #[test]
    fn rollback_ignores_unrelated_connections() {
        let before = RuleCheckpointConnections {
            connections: vec![("old".into(), "eth1".into(), 2)],
        };
        for state in [1, 2] {
            let current = RuleCheckpointConnections {
                connections: vec![
                    ("old".into(), "eth1".into(), 2),
                    ("new".into(), "eth2".into(), state),
                ],
            };
            assert!(connections_settled(&before, &current, &[]));
        }
    }

    #[test]
    fn rollback_waits_for_connection_teardown() {
        let before = RuleCheckpointConnections {
            connections: vec![("old".into(), "eth1".into(), 2)],
        };
        for state in [0, 3, 4] {
            let current = RuleCheckpointConnections {
                connections: vec![
                    ("old".into(), "eth1".into(), 2),
                    ("new".into(), "eth2".into(), state),
                ],
            };
            assert!(!connections_settled(&before, &current, &[]));
        }
    }

    #[test]
    fn rollback_waits_for_device_without_active_connection() {
        let empty = RuleCheckpointConnections::default();
        let mut device = NmDevice {
            state: NmDeviceState::Deactivating,
            ..Default::default()
        };
        assert!(!connections_settled(
            &empty,
            &empty,
            std::slice::from_ref(&device),
        ));
        device.state = NmDeviceState::Disconnected;
        assert!(connections_settled(
            &empty,
            &empty,
            std::slice::from_ref(&device),
        ));
    }
}
