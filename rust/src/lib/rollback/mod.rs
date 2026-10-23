// SPDX-License-Identifier: Apache-2.0

mod ipc;
mod journal;
mod route_rule;

use std::{sync::Arc, time::Duration};

use journal::{Identity, Journal, Namespace, Phase, RuleStep, Store};
pub(crate) use route_rule::{RouteRuleRemoval, RouteRuleRemoveError};
use tokio::sync::Mutex;

use crate::{
    ErrorKind, MergedRouteRules, NetworkState, NmstateError,
    nm::{
        nm_checkpoint_create, nm_checkpoint_destroy, nm_checkpoint_exists,
        nm_checkpoint_owner, nm_checkpoint_rollback_for_rules,
        nm_checkpoint_rule_connections, nm_checkpoint_timeout_disable,
    },
};

tokio::task_local! {
    static ACTIVE: Context;
}

#[derive(Clone)]
pub(crate) struct Context {
    inner: Arc<Mutex<Option<Journal>>>,
    store: Store,
}

impl Context {
    fn load() -> Result<Self, NmstateError> {
        let store = Store::new();
        let journal = store.load()?;
        Ok(Self {
            inner: Arc::new(Mutex::new(journal)),
            store,
        })
    }

    pub(crate) async fn begin(
        &self,
        timeout: u32,
    ) -> Result<String, NmstateError> {
        let mut guard = self.inner.lock().await;
        if guard.is_some() {
            return Err(failure(
                "An external-rule transaction is already pending",
            ));
        }
        let identity = current_identity().await?;
        let initial_rules =
            Some(RouteRuleRemoval::prepare(|_| true).await.map_err(|e| {
                failure(format!("Cannot snapshot initial routing rules: {e}"))
            })?);
        let connections = nm_checkpoint_rule_connections().await?;
        connections.validate_for_checkpoint()?;
        // A crash before the journal exists must not leave a checkpoint
        // without a rollback timeout.
        let checkpoint = nm_checkpoint_create(timeout.max(60)).await?;
        if identity != current_identity().await? {
            return Err(failure(
                "NetworkManager changed while creating the checkpoint",
            ));
        }
        let mut record = Journal::new(
            identity,
            checkpoint.clone(),
            deadline(timeout)?,
            connections,
            initial_rules,
        );
        if let Err(error) = self.store.save(&record) {
            let _ = nm_checkpoint_destroy(&checkpoint).await;
            return Err(error);
        }
        *guard = Some(record.clone());
        nm_checkpoint_timeout_disable(&checkpoint).await?;
        record.phase = Phase::Applying;
        self.store.save(&record)?;
        *guard = Some(record);
        Ok(checkpoint)
    }

    pub(crate) async fn remove_rules(
        &self,
        rules: &MergedRouteRules,
    ) -> Result<(), NmstateError> {
        let initial_rules = self
            .inner
            .lock()
            .await
            .as_ref()
            .and_then(|record| record.initial_rules.clone())
            .ok_or_else(|| failure("No initial routing rule snapshot"))?;
        let removal =
            RouteRuleRemoval::prepare_with_baseline(&initial_rules, |rule| {
                crate::nispor::kernel_rule_is_absent(rule, rules)
            })
            .await
            .map_err(|e| {
                failure(format!("Cannot prepare rule removal: {e}"))
            })?;
        if removal.is_empty() {
            return Ok(());
        }
        let mut guard = self.inner.lock().await;
        let record = guard
            .as_ref()
            .ok_or_else(|| failure("No recovery checkpoint"))?;
        if record.phase != Phase::Applying {
            return Err(failure("Rule removal requires an active apply"));
        }
        self.verify_identity(record).await?;
        let mut next = record.clone();
        next.rules.push(RuleStep {
            removal: removal.clone(),
            restoration: None,
            restored: false,
        });
        self.store.save(&next)?;
        *guard = Some(next);
        drop(guard);
        match removal.execute().await {
            Ok(()) => Ok(()),
            Err(RouteRuleRemoveError::PermissionDeniedBeforeChange(error)) => {
                let mut guard = self.inner.lock().await;
                let mut next = guard.as_ref().unwrap().clone();
                next.rules.pop();
                self.store.save(&next)?;
                *guard = Some(next);
                log::warn!(
                    "Cannot remove external rules: {error}; applying profile \
                     rules only"
                );
                Ok(())
            }
            Err(error) => {
                Err(failure(format!("Cannot remove external rules: {error}")))
            }
        }
    }

    async fn run_apply(
        &self,
        state: &NetworkState,
    ) -> Result<String, NmstateError> {
        ACTIVE
            .scope(self.clone(), async {
                state
                    .apply_with_nm_backend_context(Some(self.clone()))
                    .await
            })
            .await?;
        let mut guard = self.inner.lock().await;
        let mut record = guard
            .as_ref()
            .ok_or_else(|| {
                failure("Apply returned without a recovery checkpoint")
            })?
            .clone();
        if record.phase != Phase::Applying {
            return Err(failure("Unexpected checkpoint phase after apply"));
        }
        self.verify_identity(&record).await?;
        if expired(&record)? {
            return Err(failure("Checkpoint expired before apply completed"));
        }
        record.phase = Phase::Pending;
        self.store.save(&record)?;
        let checkpoint = record.checkpoint.clone();
        *guard = Some(record);
        Ok(checkpoint)
    }

    async fn refresh(
        &self,
        checkpoint: &str,
        seconds: u32,
    ) -> Result<bool, NmstateError> {
        let mut guard = self.inner.lock().await;
        let Some(record) = guard.as_ref().filter(|r| r.matches(checkpoint))
        else {
            return Ok(false);
        };
        if record.phase != Phase::Applying {
            return Err(failure("Cannot renew a checkpoint outside its apply"));
        }
        if expired(record)? {
            return Err(failure("Checkpoint deadline expired before renewal"));
        }
        self.verify_identity(record).await?;
        if !nm_checkpoint_exists(&record.checkpoint).await? {
            return Err(failure(
                "NetworkManager checkpoint disappeared during apply",
            ));
        }
        if expired(record)? {
            return Err(failure(
                "Checkpoint expired while renewing its deadline",
            ));
        }
        let mut next = record.clone();
        next.deadline_ms = deadline(seconds)?;
        self.store.save(&next)?;
        *guard = Some(next);
        Ok(true)
    }

    async fn verify_identity(
        &self,
        record: &Journal,
    ) -> Result<(), NmstateError> {
        if record.identity != current_identity().await? {
            return Err(failure(
                "Recovery identity changed; the journal is retained and \
                 automatic restoration is stopped",
            ));
        }
        Ok(())
    }

    async fn finish(
        &self,
        checkpoint: &str,
        commit: bool,
    ) -> Result<bool, NmstateError> {
        tokio::time::timeout(
            Duration::from_secs(45),
            self.finish_inner(checkpoint, commit),
        )
        .await
        .map_err(|_| {
            failure(
                "Rollback service operation timed out; the recovery journal \
                 is retained",
            )
        })?
    }

    async fn finish_inner(
        &self,
        checkpoint: &str,
        commit: bool,
    ) -> Result<bool, NmstateError> {
        let mut guard = self.inner.lock().await;
        let Some(record) = guard.as_ref().filter(|r| r.matches(checkpoint))
        else {
            return Ok(false);
        };
        if let Phase::Unresolved(reason) = &record.phase {
            return Err(failure(reason.clone()));
        }
        let identity = current_identity().await?;
        if record.identity != identity {
            return self.unresolved(
                &mut guard,
                "Recovery identity changed; retained journal requires \
                 explicit recovery",
            );
        }
        let exists = nm_checkpoint_exists(&record.checkpoint).await?;
        if !exists && record.phase == Phase::Preparing {
            self.store.clear()?;
            *guard = None;
            return Ok(true);
        }
        if !exists && !matches!(record.phase, Phase::Commit | Phase::Rollback) {
            return self.unresolved(
                &mut guard,
                "NetworkManager checkpoint disappeared without a recorded \
                 decision; retained journal requires explicit recovery",
            );
        }
        let commit_expired =
            commit && record.phase == Phase::Pending && expired(record)?;
        let target = decision(&record.phase, commit && !commit_expired)?;
        let mut next = record.clone();
        next.phase = target.clone();
        self.store.save(&next)?;
        *guard = Some(next);

        if target == Phase::Commit {
            if exists {
                nm_checkpoint_destroy(&guard.as_ref().unwrap().checkpoint)
                    .await?;
            }
        } else {
            self.restore(&mut guard).await?;
        }
        if guard.as_ref().unwrap().identity != current_identity().await? {
            return self.unresolved(
                &mut guard,
                "Recovery identity changed while completing the transaction; \
                 retained journal requires explicit recovery",
            );
        }
        self.store.clear()?;
        *guard = None;
        if commit_expired {
            Err(failure(
                "Checkpoint expired and was rolled back before commit",
            ))
        } else {
            Ok(true)
        }
    }

    fn unresolved(
        &self,
        guard: &mut Option<Journal>,
        reason: &str,
    ) -> Result<bool, NmstateError> {
        let mut next = guard.as_ref().unwrap().clone();
        next.phase = Phase::Unresolved(reason.into());
        self.store.save(&next)?;
        *guard = Some(next);
        Err(failure(reason))
    }

    async fn restore(
        &self,
        guard: &mut Option<Journal>,
    ) -> Result<(), NmstateError> {
        let record = guard.as_ref().unwrap().clone();
        if !record.nm_finished {
            // This also settles a rollback completed before the helper
            // restarted.
            match nm_checkpoint_rollback_for_rules(
                &record.checkpoint,
                &record.connections,
            )
            .await
            {
                Ok(()) => {
                    let mut next = record.clone();
                    next.nm_finished = true;
                    self.store.save(&next)?;
                    *guard = Some(next);
                }
                Err(error) => {
                    self.verify_recovery_identity(guard).await?;
                    if nm_checkpoint_exists(&record.checkpoint).await? {
                        return Err(error);
                    }
                    return self
                        .unresolved(
                            guard,
                            &format!(
                                "{error}; NetworkManager checkpoint is gone \
                                 and rollback failed; retained journal \
                                 requires explicit recovery"
                            ),
                        )
                        .map(|_| ());
                }
            }
        }
        for index in (0..guard.as_ref().unwrap().rules.len()).rev() {
            let record = guard.as_ref().unwrap().clone();
            if record.rules[index].restored {
                continue;
            }
            self.verify_recovery_identity(guard).await?;
            if record.rules[index].restoration.is_none() {
                let plan = record.rules[index]
                    .removal
                    .prepare_restore()
                    .await
                    .map_err(|e| {
                        failure(format!("Cannot prepare rule restoration: {e}"))
                    })?;
                let mut next = record.clone();
                next.rules[index].restoration = Some(plan);
                self.store.save(&next)?;
                *guard = Some(next);
            }
            guard.as_ref().unwrap().rules[index]
                .restoration
                .as_ref()
                .unwrap()
                .restore_prepared()
                .await
                .map_err(|e| {
                    failure(format!("Cannot restore external rules: {e}"))
                })?;
            let mut next = guard.as_ref().unwrap().clone();
            next.rules[index].restored = true;
            self.store.save(&next)?;
            *guard = Some(next);
        }
        Ok(())
    }

    async fn verify_recovery_identity(
        &self,
        guard: &mut Option<Journal>,
    ) -> Result<(), NmstateError> {
        if guard.as_ref().unwrap().identity != current_identity().await? {
            self.unresolved(
                guard,
                "Recovery identity changed during restoration; retained \
                 journal requires explicit recovery",
            )?;
        }
        Ok(())
    }

    async fn recover(&self) -> Result<(), NmstateError> {
        let phase = self.inner.lock().await.as_ref().map(|r| r.phase.clone());
        match phase {
            Some(Phase::Preparing | Phase::Applying | Phase::Rollback) => {
                self.finish("", false).await?;
            }
            Some(Phase::Commit) => {
                self.finish("", true).await?;
            }
            Some(Phase::Pending) => {
                let guard = self.inner.lock().await;
                let record = guard.as_ref().unwrap();
                let mismatch = record.identity != current_identity().await?;
                let missing = !nm_checkpoint_exists(&record.checkpoint).await?;
                let expired = expired(record)?;
                drop(guard);
                if mismatch || missing || expired {
                    self.finish("", false).await?;
                }
            }
            Some(Phase::Unresolved(reason)) => return Err(failure(reason)),
            None => (),
        }
        Ok(())
    }

    async fn wait_for_deadline(&self) -> Result<(), NmstateError> {
        loop {
            let remaining = {
                let guard = self.inner.lock().await;
                match guard.as_ref() {
                    Some(Journal {
                        phase: Phase::Applying | Phase::Pending,
                        deadline_ms: Some(d),
                        ..
                    }) => Some(d.saturating_sub(boottime_ms()?)),
                    _ => None,
                }
            };
            match remaining {
                Some(0) => return Ok(()),
                Some(ms) => {
                    tokio::time::sleep(Duration::from_millis(ms.min(1000)))
                        .await
                }
                None => tokio::time::sleep(Duration::from_secs(1)).await,
            }
        }
    }
}

fn decision(phase: &Phase, commit: bool) -> Result<Phase, NmstateError> {
    match (phase, commit) {
        (Phase::Pending, true) | (Phase::Commit, true) => Ok(Phase::Commit),
        (
            Phase::Preparing
            | Phase::Applying
            | Phase::Pending
            | Phase::Rollback,
            false,
        ) => Ok(Phase::Rollback),
        _ => Err(failure("Checkpoint already has a conflicting decision")),
    }
}

pub(crate) async fn refresh_owned(
    checkpoint: &str,
    seconds: u32,
) -> Result<bool, NmstateError> {
    match ACTIVE.try_with(Clone::clone) {
        Ok(context) => context.refresh(checkpoint, seconds).await,
        Err(_) => Ok(false),
    }
}

pub(crate) async fn apply(state: &NetworkState) -> Result<(), NmstateError> {
    let checkpoint = ipc::apply(state).await?;
    if !state.no_commit && !finish(&checkpoint, true).await? {
        return Err(failure(
            "Recovery service lost the checkpoint before commit",
        ));
    }
    Ok(())
}

pub(crate) fn has_host_net_admin() -> Result<bool, NmstateError> {
    ipc::has_host_net_admin()
}

pub(crate) async fn finish(
    checkpoint: &str,
    commit: bool,
) -> Result<bool, NmstateError> {
    ipc::finish(checkpoint, commit).await
}

pub(crate) async fn run_service() -> Result<(), NmstateError> {
    ipc::run_service().await
}

async fn current_identity() -> Result<Identity, NmstateError> {
    tokio::time::timeout(Duration::from_secs(10), query_identity())
        .await
        .map_err(|_| failure("Timed out verifying recovery identity"))?
}

async fn query_identity() -> Result<Identity, NmstateError> {
    let namespace = Namespace::read("/proc/self/ns/net")?;
    let user_namespace = Namespace::read("/proc/self/ns/user")?;
    if namespace != Namespace::read("/proc/1/ns/net")? {
        return Err(permission(
            "Recovery service requires the host network namespace",
        ));
    }
    if user_namespace != Namespace::read("/proc/1/ns/user")? {
        return Err(permission("Recovery requires the host user namespace"));
    }
    let owner = nm_checkpoint_owner().await?;
    let connection = zbus::Connection::system()
        .await
        .map_err(|e| failure(format!("Cannot connect to D-Bus: {e}")))?;
    let proxy = zbus::Proxy::new(
        &connection,
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
    )
    .await
    .map_err(|e| {
        failure(format!("Cannot inspect NetworkManager owner: {e}"))
    })?;
    let pid: u32 = proxy
        .call("GetConnectionUnixProcessID", &(&owner,))
        .await
        .map_err(|e| {
        failure(format!("Cannot inspect NetworkManager process: {e}"))
    })?;
    let uid: u32 = proxy
        .call("GetConnectionUnixUser", &(&owner,))
        .await
        .map_err(|e| {
            failure(format!("Cannot inspect NetworkManager credentials: {e}"))
        })?;
    if uid != 0
        || Namespace::read(format!("/proc/{pid}/ns/net"))? != namespace
        || Namespace::read(format!("/proc/{pid}/ns/user"))? != user_namespace
    {
        return Err(permission(
            "NetworkManager must run as root in the recovery service user and \
             network namespaces",
        ));
    }
    let bus_id: String = proxy.call("GetId", &()).await.map_err(|e| {
        failure(format!("Cannot inspect system bus identity: {e}"))
    })?;
    let boot = std::fs::read_to_string("/proc/sys/kernel/random/boot_id")
        .map_err(|e| failure(format!("Cannot read boot identity: {e}")))?;
    Ok(Identity {
        boot: boot.trim().into(),
        namespace,
        user_namespace,
        nm_owner: owner,
        bus_id,
    })
}

fn boottime_ms() -> Result<u64, NmstateError> {
    let mut time = nix::libc::timespec {
        tv_sec: 0,
        tv_nsec: 0,
    };
    // CLOCK_BOOTTIME includes suspend and remains comparable across helper
    // restarts.
    if unsafe { nix::libc::clock_gettime(nix::libc::CLOCK_BOOTTIME, &mut time) }
        != 0
    {
        return Err(failure(format!(
            "Cannot read monotonic clock: {}",
            std::io::Error::last_os_error()
        )));
    }
    Ok(time.tv_sec as u64 * 1000 + time.tv_nsec as u64 / 1_000_000)
}

fn deadline(seconds: u32) -> Result<Option<u64>, NmstateError> {
    Ok(if seconds == 0 {
        None
    } else {
        Some(boottime_ms()? + u64::from(seconds) * 1000)
    })
}

fn expired(record: &Journal) -> Result<bool, NmstateError> {
    match record.deadline_ms {
        Some(deadline) => Ok(boottime_ms()? >= deadline),
        None => Ok(false),
    }
}

fn failure(message: impl Into<String>) -> NmstateError {
    NmstateError::new(ErrorKind::PluginFailure, message.into())
}

fn permission(message: impl Into<String>) -> NmstateError {
    NmstateError::new(ErrorKind::PermissionError, message.into())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn durable_decision_cannot_be_reversed() {
        assert!(decision(&Phase::Commit, false).is_err());
        assert!(decision(&Phase::Rollback, true).is_err());
        assert_eq!(decision(&Phase::Commit, true).unwrap(), Phase::Commit);
        assert_eq!(decision(&Phase::Rollback, false).unwrap(), Phase::Rollback);
    }

    #[test]
    fn interrupted_apply_must_rollback() {
        assert!(decision(&Phase::Applying, true).is_err());
        assert!(decision(&Phase::Preparing, true).is_err());
        assert_eq!(decision(&Phase::Applying, false).unwrap(), Phase::Rollback);
        assert_eq!(
            decision(&Phase::Preparing, false).unwrap(),
            Phase::Rollback
        );
    }

    #[test]
    fn unresolved_transaction_never_automatically_finishes() {
        let phase = Phase::Unresolved("NM restarted".into());
        assert!(decision(&phase, true).is_err());
        assert!(decision(&phase, false).is_err());
    }
}
