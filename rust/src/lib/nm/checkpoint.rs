// SPDX-License-Identifier: Apache-2.0

use std::time::{Duration, Instant};

use log::warn;

use crate::{
    ErrorKind, NmstateError,
    nm::{
        error::nm_error_to_nmstate,
        nm_dbus::{
            NmActiveConnection, NmActiveConnectionState, NmApi, NmDevice,
            NmDeviceState,
        },
    },
};

pub(crate) async fn nm_checkpoint_owner() -> Result<String, NmstateError> {
    async { NmApi::new().await?.name_owner().await }
        .await
        .map_err(|e| NmstateError::new(ErrorKind::PluginFailure, e.msg))
}

pub(crate) async fn nm_checkpoint_exists(
    checkpoint: &str,
) -> Result<bool, NmstateError> {
    let nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_exists(checkpoint)
        .await
        .map_err(nm_error_to_nmstate)
}

pub(crate) async fn nm_checkpoint_timeout_disable(
    checkpoint: &str,
) -> Result<(), NmstateError> {
    let nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    nm_api
        .checkpoint_timeout_disable(checkpoint)
        .await
        .map_err(nm_error_to_nmstate)
}

// Journal version 1 stores each connection as [uuid, iface_name, state].
#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(from = "(String, String, u32)", into = "(String, String, u32)")]
struct RuleCheckpointConnection {
    uuid: String,
    iface_name: String,
    state: NmActiveConnectionState,
}

impl From<(String, String, u32)> for RuleCheckpointConnection {
    fn from((uuid, iface_name, state): (String, String, u32)) -> Self {
        Self {
            uuid,
            iface_name,
            state: state.into(),
        }
    }
}

impl From<RuleCheckpointConnection> for (String, String, u32) {
    fn from(connection: RuleCheckpointConnection) -> Self {
        (
            connection.uuid,
            connection.iface_name,
            connection.state.into(),
        )
    }
}

impl From<NmActiveConnection> for RuleCheckpointConnection {
    fn from(connection: NmActiveConnection) -> Self {
        Self {
            uuid: connection.uuid,
            iface_name: connection.iface_name,
            state: connection.state,
        }
    }
}

#[derive(Clone, Debug, Default, serde::Serialize, serde::Deserialize)]
pub(crate) struct RuleCheckpointConnections {
    connections: Vec<RuleCheckpointConnection>,
}

impl RuleCheckpointConnections {
    pub(crate) fn validate_for_checkpoint(&self) -> Result<(), NmstateError> {
        if self.connections.iter().any(|connection| {
            !matches!(
                connection.state,
                NmActiveConnectionState::Activating
                    | NmActiveConnectionState::Activated
            )
        }) {
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
            .map(RuleCheckpointConnection::from)
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
        .checkpoint_exists(checkpoint)
        .await
        .map_err(nm_error_to_nmstate)?
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
            .checkpoint_rollback(checkpoint)
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
            // States can look settled while NM still has work queued.
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

// NM can consider a deactivating connection unchanged and skip its
// reactivation during rollback.
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

// active_connections_get() skips active connections whose profile is
// already gone, while their devices can still be deactivating.
fn deactivation_finished(
    devices: &[NmDevice],
    connections: &[NmActiveConnection],
) -> bool {
    devices
        .iter()
        .all(|device| device.state != NmDeviceState::Deactivating)
        && connections.iter().all(|connection| {
            !matches!(
                connection.state,
                NmActiveConnectionState::Deactivating
                    | NmActiveConnectionState::Deactivated
            )
        })
}

// Baseline connections that were still activating, e.g. waiting for DHCP,
// may fail after rollback, and unrelated connections may appear.
fn connections_settled(
    baseline: &RuleCheckpointConnections,
    current: &RuleCheckpointConnections,
    devices: &[NmDevice],
) -> bool {
    deactivation_finished(devices, &[])
        && current.connections.iter().all(|connection| {
            matches!(
                connection.state,
                NmActiveConnectionState::Activating
                    | NmActiveConnectionState::Activated
            )
        })
        && baseline
            .connections
            .iter()
            .filter(|saved| saved.state == NmActiveConnectionState::Activated)
            .all(|saved| current.connections.contains(saved))
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
    use NmActiveConnectionState::{
        Activated, Activating, Deactivated, Deactivating, Other, Unknown,
    };

    use super::*;

    fn rule_connection(
        uuid: &str,
        iface_name: &str,
        state: NmActiveConnectionState,
    ) -> RuleCheckpointConnection {
        RuleCheckpointConnection {
            uuid: uuid.into(),
            iface_name: iface_name.into(),
            state,
        }
    }

    #[test]
    fn checkpoint_connections_preserve_v1_journal_format() {
        let saved = serde_json::json!({
            "connections": [
                ["uuid", "eth0", 0],
                ["uuid", "eth1", 1],
                ["uuid", "eth2", 2],
                ["uuid", "eth3", 3],
                ["uuid", "eth4", 4],
                ["uuid", "eth5", u32::MAX],
            ]
        });
        let connections: RuleCheckpointConnections =
            serde_json::from_value(saved.clone()).unwrap();
        let first = &connections.connections[0];
        assert_eq!(
            (first.uuid.as_str(), first.iface_name.as_str()),
            ("uuid", "eth0")
        );
        assert_eq!(
            connections
                .connections
                .iter()
                .map(|connection| connection.state)
                .collect::<Vec<_>>(),
            vec![
                Unknown,
                Activating,
                Activated,
                Deactivating,
                Deactivated,
                Other(u32::MAX),
            ]
        );
        assert_eq!(serde_json::to_value(connections).unwrap(), saved);
        let from_nm = RuleCheckpointConnection::from(NmActiveConnection {
            uuid: "uuid".into(),
            iface_name: "eth0".into(),
            state: Activated,
            ..Default::default()
        });
        assert_eq!(
            serde_json::to_value(from_nm).unwrap(),
            serde_json::json!(["uuid", "eth0", 2])
        );
    }

    #[test]
    fn checkpoint_rejects_ambiguous_deactivation_baseline() {
        for state in [Unknown, Deactivating, Deactivated, Other(u32::MAX)] {
            assert!(
                RuleCheckpointConnections {
                    connections: vec![rule_connection("uuid", "eth1", state)],
                }
                .validate_for_checkpoint()
                .is_err()
            );
        }
        for state in [Activating, Activated] {
            assert!(
                RuleCheckpointConnections {
                    connections: vec![rule_connection("uuid", "eth1", state)],
                }
                .validate_for_checkpoint()
                .is_ok()
            );
        }
        assert!(
            RuleCheckpointConnections {
                connections: vec![
                    rule_connection("up", "eth1", Activated),
                    rule_connection("down", "eth2", Deactivating),
                ],
            }
            .validate_for_checkpoint()
            .is_err()
        );
        assert!(
            RuleCheckpointConnections::default()
                .validate_for_checkpoint()
                .is_ok()
        );
    }

    #[test]
    fn rollback_ignores_unchanged_dhcp_activation() {
        let before = RuleCheckpointConnections {
            connections: vec![rule_connection("uuid", "eth1", Activating)],
        };
        assert!(connections_settled(&before, &before, &[]));
        let current = RuleCheckpointConnections {
            connections: vec![rule_connection("uuid", "eth1", Activated)],
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
        for state in [Deactivating, Deactivated] {
            assert!(!deactivation_finished(
                std::slice::from_ref(&device),
                &[NmActiveConnection {
                    state,
                    ..Default::default()
                }],
            ));
        }
        assert!(deactivation_finished(std::slice::from_ref(&device), &[]));
        for state in [Unknown, Activating, Activated, Other(u32::MAX)] {
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
            connections: vec![rule_connection("old", "eth1", Activated)],
        };
        for current in [
            vec![rule_connection("old", "eth1", Activating)],
            vec![rule_connection("new", "eth1", Activated)],
            vec![rule_connection("old", "eth2", Activated)],
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
            connections: vec![rule_connection("old", "eth1", Activated)],
        };
        for state in [Activating, Activated] {
            let current = RuleCheckpointConnections {
                connections: vec![
                    rule_connection("old", "eth1", Activated),
                    rule_connection("new", "eth2", state),
                ],
            };
            assert!(connections_settled(&before, &current, &[]));
        }
    }

    #[test]
    fn rollback_waits_for_connection_teardown() {
        let before = RuleCheckpointConnections {
            connections: vec![rule_connection("old", "eth1", Activated)],
        };
        for state in [Unknown, Deactivating, Deactivated, Other(u32::MAX)] {
            let current = RuleCheckpointConnections {
                connections: vec![
                    rule_connection("old", "eth1", Activated),
                    rule_connection("new", "eth2", state),
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
