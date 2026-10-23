// SPDX-License-Identifier: Apache-2.0

use std::future::Future;

use futures_util::future::{Either, select};

use crate::{
    ErrorKind, MergedInterfaces, MergedNetworkState, MergedRouteRules,
    NetworkState, NetworkStateMode, NmstateError,
    nispor::{
        apply_ifaces_alt_names, nispor_apply, nispor_retrieve,
        persist_alt_name_config, route_rule_worker_needed,
        set_running_hostname,
    },
    nm::{
        nm_apply, nm_checkpoint_create, nm_checkpoint_destroy,
        nm_checkpoint_rollback, nm_checkpoint_timeout_extend, nm_retrieve,
    },
    ovsdb::{
        DEFAULT_OVS_DB_SOCKET_PATH, ovsdb_apply_global_conf, ovsdb_is_running,
        ovsdb_retrieve,
    },
};

const DEFAULT_ROLLBACK_TIMEOUT: u32 = 60;
const VERIFY_RETRY_INTERVAL_MILLISECONDS: u64 = 1000;
const VERIFY_RETRY_COUNT_DEFAULT: usize = 5;
const VERIFY_RETRY_COUNT_OVS: usize = 10;
const VERIFY_RETRY_COUNT_SRIOV_MIN: usize = 30;
const VERIFY_RETRY_COUNT_SRIOV_MAX: usize = 300;
const VERIFY_RETRY_COUNT_KERNEL_MODE: usize = 5;
const RETRY_NM_COUNT: usize = 2;
const RETRY_NM_INTERVAL_MILLISECONDS: u64 = 2000;

const MAX_SUPPORTED_INTERFACES: usize = 1000;

impl NetworkState {
    /// Rollback a checkpoint.
    /// Not available for `kernel only` mode.
    /// Only available for feature `query_apply`.
    pub fn checkpoint_rollback(checkpoint: &str) -> Result<(), NmstateError> {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_io()
            .enable_time()
            .build()
            .map_err(|e| {
                NmstateError::new(
                    ErrorKind::Bug,
                    format!("tokio::runtime::Builder failed with {e}"),
                )
            })?;
        rt.block_on(Self::checkpoint_rollback_async(checkpoint))
    }

    /// Rollback a checkpoint.
    /// Not available for `kernel only` mode.
    /// Only available for feature `query_apply`.
    pub async fn checkpoint_rollback_async(
        checkpoint: &str,
    ) -> Result<(), NmstateError> {
        if crate::rollback::finish(checkpoint, false).await? {
            return Ok(());
        }
        nm_checkpoint_rollback(checkpoint).await
    }

    /// Commit a checkpoint.
    /// Not available for `kernel only` mode.
    /// Only available for feature `query_apply`.
    pub fn checkpoint_commit(checkpoint: &str) -> Result<(), NmstateError> {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_io()
            .enable_time()
            .build()
            .map_err(|e| {
                NmstateError::new(
                    ErrorKind::Bug,
                    format!("tokio::runtime::Builder failed with {e}"),
                )
            })?;
        rt.block_on(Self::checkpoint_commit_async(checkpoint))
    }

    /// Commit a checkpoint.
    /// Not available for `kernel only` mode.
    /// Only available for feature `query_apply`.
    pub async fn checkpoint_commit_async(
        checkpoint: &str,
    ) -> Result<(), NmstateError> {
        if crate::rollback::finish(checkpoint, true).await? {
            return Ok(());
        }
        nm_checkpoint_destroy(checkpoint).await
    }

    /// Retrieve the `NetworkState`.
    /// Only available for feature `query_apply`.
    pub fn retrieve(&mut self) -> Result<&mut Self, NmstateError> {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_io()
            .enable_time()
            .build()
            .map_err(|e| {
                NmstateError::new(
                    ErrorKind::Bug,
                    format!("tokio::runtime::Builder failed with {e}"),
                )
            })?;
        rt.block_on(self.retrieve_async())
    }

    /// Retrieve the `NetworkState`.
    /// Only available for feature `query_apply`.
    pub async fn retrieve_async(&mut self) -> Result<&mut Self, NmstateError> {
        let state = nispor_retrieve(
            self.running_config_only,
            self.kernel_only,
            self.route_rules_for_apply,
        )
        .await?;
        self.hostname = state.hostname;
        self.interfaces = state.interfaces;
        self.routes = state.routes;
        self.rules = state.rules;
        self.dns = state.dns;
        if ovsdb_is_running().await {
            match ovsdb_retrieve().await {
                Ok(mut ovsdb_state) => {
                    ovsdb_state.isolate_ovn()?;
                    self.update_state(&ovsdb_state);
                }
                Err(e) => {
                    log::warn!("Failed to retrieve OVS DB state: {e}");
                }
            }
        }
        if !self.kernel_only {
            let nm_state = nm_retrieve(self.running_config_only, self).await?;
            // TODO: Priority handling
            self.update_state(&nm_state);
        }
        if !self.include_secrets {
            self.hide_secrets();
        }

        // Purge user space ignored interfaces
        self.interfaces
            .user_ifaces
            .retain(|_, iface| !iface.is_ignore());

        // Mark routes next hop to ignored interface as ignored
        self.routes.apply_ignored_ifaces(&self.interfaces);

        // A kernel booted with `ipv6.disable=1` has no IPv6 stack, but NM
        // profiles using `method=auto` would still report `ipv6.enabled: true`.
        // Force IPv6 off everywhere in that case. IPv6 can also be disabled per
        // interface while the stack is present; handle those individually.
        let kernel_disabled = ipv6_disabled_in_kernel();
        self.interfaces.disable_ipv6_where(|name| {
            kernel_disabled || ipv6_disabled_in_kernel_for_iface(name)
        });

        Ok(self)
    }

    /// Apply the `NetworkState`.
    /// Only available for feature `query_apply`.
    pub fn apply(&self) -> Result<(), NmstateError> {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_io()
            .enable_time()
            .build()
            .map_err(|e| {
                NmstateError::new(
                    ErrorKind::Bug,
                    format!("tokio::runtime::Builder failed with {e}"),
                )
            })?;
        rt.block_on(self.apply_async())
    }

    /// Apply the `NetworkState`.
    /// Only available for feature `query_apply`.
    pub async fn apply_async(&self) -> Result<(), NmstateError> {
        if self.override_iface {
            log::warn!(
                "override_iface is deprecated; specify interface settings \
                 explicitly in the desired state instead"
            );
        }
        if self.interfaces.kernel_ifaces.len()
            + self.interfaces.user_ifaces.len()
            >= MAX_SUPPORTED_INTERFACES
        {
            log::warn!(
                "Interfaces count exceeds the support limit \
                 {MAX_SUPPORTED_INTERFACES} in desired state",
            );
        }
        if self.interfaces.has_up_ovs_iface() && !ovsdb_is_running().await {
            if self.no_verify {
                log::warn!(
                    "Desired state contains OVS interfaces, but not able to \
                     connect OVS daemon at socket {DEFAULT_OVS_DB_SOCKET_PATH}"
                );
            } else {
                let e = NmstateError::new(
                    ErrorKind::PluginFailure,
                    format!(
                        "Desired state contains OVS interfaces, but not able \
                         to connect OVS daemon at socket \
                         {DEFAULT_OVS_DB_SOCKET_PATH}"
                    ),
                );
                log::error!("{e}");
                return Err(e);
            }
        }

        if !self.kernel_only {
            self.apply_with_nm_backend().await
        } else {
            // TODO: Need checkpoint for kernel only mode
            self.apply_without_nm_backend().await
        }
    }

    async fn apply_with_nm_backend(&self) -> Result<(), NmstateError> {
        self.apply_with_nm_backend_context(None).await
    }

    pub(crate) async fn apply_with_nm_backend_context(
        &self,
        context: Option<crate::rollback::Context>,
    ) -> Result<(), NmstateError> {
        let mut merged_state = None;
        let mut cur_net_state = NetworkState::new();
        cur_net_state.set_kernel_only(self.kernel_only);
        cur_net_state.set_include_secrets(true);
        cur_net_state.route_rules_for_apply = true;
        if let Err(e) = cur_net_state.retrieve_async().await {
            if e.kind().can_retry() {
                log::info!("Retrying on: {e}");
                tokio::time::sleep(std::time::Duration::from_millis(
                    RETRY_NM_INTERVAL_MILLISECONDS,
                ))
                .await;
                cur_net_state.retrieve_async().await?;
            } else {
                return Err(e);
            }
        }

        // At this point, the `unknown` interface type is not resolved yet,
        // hence when user want `enable-and-use` single-transaction for SR-IOV,
        // they need define the interface type. It is overkill to do resolve at
        // this point for this corner use case.
        let pf_state = if self.has_sriov_and_missing_eth(&cur_net_state) {
            self.get_sriov_pf_conf_state()
        } else {
            None
        };

        if pf_state.is_none() {
            // Do early pre-apply validation before checkpoint.
            merged_state = Some(MergedNetworkState::new(
                self.clone(),
                cur_net_state.clone(),
                NetworkStateMode::Apply,
                self.memory_only,
            )?);
        }

        let timeout = if let Some(t) = self.timeout {
            t
        } else if pf_state.is_some() {
            VERIFY_RETRY_COUNT_SRIOV_MAX as u32
        } else {
            DEFAULT_ROLLBACK_TIMEOUT
        };

        if context.is_none() {
            let rules = MergedRouteRules::new(
                self.rules.clone(),
                cur_net_state.rules.clone(),
            )?;
            let rules =
                merged_state.as_ref().map(|m| &m.rules).unwrap_or(&rules);
            if route_rule_worker_needed(rules, &cur_net_state).await? {
                if crate::rollback::has_host_net_admin()? {
                    return crate::rollback::apply(self).await;
                }
                return Err(NmstateError::new(
                    ErrorKind::PermissionError,
                    "Removing routing rules outside NetworkManager profiles \
                     requires CAP_NET_ADMIN"
                        .into(),
                ));
            }
        }
        let checkpoint = if let Some(context) = context.as_ref() {
            context.begin(timeout).await?
        } else {
            match nm_checkpoint_create(timeout).await {
                Ok(c) => c,
                Err(e) => {
                    if e.kind().can_retry() {
                        log::info!("Retrying on: {e}");
                        tokio::time::sleep(std::time::Duration::from_millis(
                            RETRY_NM_INTERVAL_MILLISECONDS,
                        ))
                        .await;
                        nm_checkpoint_create(timeout).await?
                    } else {
                        return Err(e);
                    }
                }
            }
        };

        log::info!("Created checkpoint {}", checkpoint);
        let apply = async {
            if let Some(pf_state) = pf_state {
                let pf_merged_state = MergedNetworkState::new(
                    pf_state,
                    cur_net_state.clone(),
                    NetworkStateMode::Apply,
                    self.memory_only,
                )?;
                let verify_count =
                    get_proper_verify_retry_count(&pf_merged_state.interfaces);
                self.apply_with_nm_backend_and_under_checkpoint(
                    &pf_merged_state,
                    &cur_net_state,
                    &checkpoint,
                    verify_count,
                    timeout,
                    context.as_ref(),
                )
                .await?;
                // Refresh current state
                cur_net_state.retrieve_async().await?;
                merged_state = Some(MergedNetworkState::new(
                    self.clone(),
                    cur_net_state.clone(),
                    NetworkStateMode::Apply,
                    self.memory_only,
                )?);
            }

            let merged_state = if let Some(merged_state) = merged_state.as_ref()
            {
                merged_state
            } else {
                return Err(NmstateError::new(
                    ErrorKind::Bug,
                    "Got unexpected None for merged_state in \
                     apply_with_nm_backend()"
                        .into(),
                ));
            };
            let verify_count =
                get_proper_verify_retry_count(&merged_state.interfaces);

            self.interfaces.check_sriov_capability()?;

            self.apply_with_nm_backend_and_under_checkpoint(
                merged_state,
                &cur_net_state,
                &checkpoint,
                verify_count,
                timeout,
                context.as_ref(),
            )
            .await
        };
        if context.is_some() {
            apply.await
        } else {
            with_nm_checkpoint(&checkpoint, self.no_commit, || apply).await
        }
    }

    async fn apply_with_nm_backend_and_under_checkpoint(
        &self,
        merged_state: &MergedNetworkState,
        cur_net_state: &Self,
        checkpoint: &str,
        retry_count: usize,
        timeout: u32,
        context: Option<&crate::rollback::Context>,
    ) -> Result<(), NmstateError> {
        // Roll back partial rule removals instead of retrying from that state.
        if let Some(context) = context {
            with_checkpoint_refresh(
                context.remove_rules(&merged_state.rules),
                timeout,
                || nm_checkpoint_timeout_extend(checkpoint, timeout),
            )
            .await?;
        }
        // NM might have unknown race problem found by verify stage,
        // we try to apply the state again if so.
        with_retry(
            RETRY_NM_INTERVAL_MILLISECONDS,
            RETRY_NM_COUNT,
            |is_retry| async move {
                nm_checkpoint_timeout_extend(checkpoint, timeout).await?;
                nm_apply(merged_state, checkpoint, timeout, is_retry).await?;
                if ovsdb_is_running().await {
                    ovsdb_apply_global_conf(merged_state).await?;
                }
                if let Some(running_hostname) =
                    self.hostname.as_ref().and_then(|c| c.running.as_ref())
                {
                    set_running_hostname(running_hostname)?;
                }

                apply_ifaces_alt_names(&merged_state.interfaces).await?;
                persist_alt_name_config(&merged_state.interfaces).await?;

                if !self.no_verify {
                    with_retry(
                        VERIFY_RETRY_INTERVAL_MILLISECONDS,
                        retry_count,
                        |_| async {
                            nm_checkpoint_timeout_extend(checkpoint, timeout)
                                .await?;
                            let mut new_cur_net_state = cur_net_state.clone();
                            new_cur_net_state.set_include_secrets(true);
                            new_cur_net_state.retrieve_async().await?;
                            merged_state.verify(&new_cur_net_state)
                        },
                    )
                    .await
                } else {
                    Ok(())
                }
            },
        )
        .await?;
        Ok(())
    }

    async fn apply_without_nm_backend(&self) -> Result<(), NmstateError> {
        let mut cur_net_state = NetworkState::new();
        cur_net_state.set_kernel_only(self.kernel_only);
        cur_net_state.set_include_secrets(true);
        cur_net_state.retrieve_async().await?;

        let merged_state = MergedNetworkState::new(
            self.clone(),
            cur_net_state.clone(),
            NetworkStateMode::Apply,
            self.memory_only,
        )?;

        nispor_apply(&merged_state).await?;
        if let Some(running_hostname) =
            self.hostname.as_ref().and_then(|c| c.running.as_ref())
        {
            set_running_hostname(running_hostname)?;
        }
        if !self.no_verify {
            with_retry(
                VERIFY_RETRY_INTERVAL_MILLISECONDS,
                VERIFY_RETRY_COUNT_KERNEL_MODE,
                |_| async {
                    let mut new_cur_net_state = cur_net_state.clone();
                    new_cur_net_state.retrieve_async().await?;
                    merged_state.verify(&new_cur_net_state)
                },
            )
            .await
        } else {
            Ok(())
        }
    }

    pub(crate) fn update_state(&mut self, other: &Self) {
        if let Some(other_hostname) = other.hostname.as_ref() {
            if let Some(h) = self.hostname.as_mut() {
                h.update(other_hostname);
            } else {
                self.hostname.clone_from(&other.hostname);
            }
        }
        self.interfaces.update(&other.interfaces);
        if other.dns.is_some() {
            self.dns.clone_from(&other.dns);
        }
        if other.ovsdb.is_some() {
            self.ovsdb.clone_from(&other.ovsdb);
        }
        if !other.ovn.is_none() {
            self.ovn = other.ovn.clone();
        }
    }

    /// Generate new NetworkState contains only changed properties
    pub fn gen_diff(&self, current: &Self) -> Result<Self, NmstateError> {
        let mut ret = Self::default();
        let merged_state = MergedNetworkState::new(
            self.clone(),
            current.clone(),
            NetworkStateMode::GenerateDiff,
            false,
        )?;

        ret.interfaces = merged_state.interfaces.gen_diff()?;
        if merged_state.dns.is_changed() {
            ret.dns.clone_from(&self.dns);
        }

        if merged_state.hostname.is_changed() {
            ret.hostname.clone_from(&self.hostname);
        }

        ret.routes = merged_state.routes.gen_diff();
        ret.rules = merged_state.rules.gen_diff();
        if self.description != current.description {
            ret.description.clone_from(&self.description);
        }

        if merged_state.ovsdb.is_changed() {
            ret.ovsdb.clone_from(&self.ovsdb);
        }

        if merged_state.ovn.is_changed() {
            ret.ovn = self.ovn.clone();
        }
        Ok(ret)
    }
}

// `/proc/sys/net/ipv6` is absent only when the kernel has no IPv6 stack at all.
// The runtime `disable_ipv6` sysctl keeps the directory present and is
// overridable per interface, so it is deliberately not forced off here.
// Only a confirmed absence counts; a probe error must not wipe IPv6 state.
fn ipv6_disabled_in_kernel() -> bool {
    matches!(
        std::path::Path::new("/proc/sys/net/ipv6").try_exists(),
        Ok(false)
    )
}

// Unlike `conf/all/disable_ipv6`, the per-interface value is a reliable signal.
// A missing file (stack absent or interface gone) means not disabled.
fn ipv6_disabled_in_kernel_for_iface(iface_name: &str) -> bool {
    std::fs::read_to_string(format!(
        "/proc/sys/net/ipv6/conf/{iface_name}/disable_ipv6"
    ))
    .is_ok_and(|v| v.trim() == "1")
}

async fn with_nm_checkpoint<T, Fut>(
    checkpoint: &str,
    no_commit: bool,
    func: T,
) -> Result<(), NmstateError>
where
    T: FnOnce() -> Fut,
    // Once `std::ops::AsyncFnOnce` is stable, use it instead
    Fut: Future<Output = Result<(), NmstateError>>,
{
    match func().await {
        Ok(()) => {
            if !no_commit {
                nm_checkpoint_destroy(checkpoint).await?;

                log::info!("Destroyed checkpoint {checkpoint}");
            } else {
                log::info!("Skipping commit for checkpoint {checkpoint}");
            }
            Ok(())
        }
        Err(e) => {
            if let Err(e) = nm_checkpoint_rollback(checkpoint).await {
                log::warn!("nm_checkpoint_rollback() failed: {e}");
            }
            log::info!("Rollbacked to checkpoint {checkpoint}");
            Err(e)
        }
    }
}

async fn with_checkpoint_refresh<F, R, RF>(
    operation: F,
    timeout: u32,
    mut refresh: R,
) -> Result<(), NmstateError>
where
    F: Future<Output = Result<(), NmstateError>>,
    R: FnMut() -> RF,
    RF: Future<Output = Result<(), NmstateError>>,
{
    refresh().await?;
    if timeout == 0 {
        return operation.await;
    }

    let interval = std::time::Duration::from_secs(u64::from(timeout)) / 2;
    let mut operation = std::pin::pin!(operation);
    loop {
        let timer = std::pin::pin!(tokio::time::sleep(interval));
        // The removal sends no requests while the checkpoint is renewed.
        match select(timer, operation.as_mut()).await {
            Either::Left(_) => refresh().await?,
            Either::Right((result, _)) => return result,
        }
    }
}

async fn with_retry<T, Fut>(
    interval_ms: u64,
    count: usize,
    func: T,
) -> Result<(), NmstateError>
where
    T: FnOnce(bool) -> Fut + Copy,
    // Once `std::ops::AsyncFnOnce` is stable, use it instead
    Fut: Future<Output = Result<(), NmstateError>>,
{
    let mut cur_count = 0usize;
    while cur_count < count {
        let is_retry = cur_count != 0;
        if let Err(e) = func(is_retry).await {
            if cur_count == count - 1 || !e.kind().can_retry() {
                if e.kind().can_ignore() {
                    return Ok(());
                } else {
                    return Err(e);
                }
            } else {
                log::info!("Retrying on: {e}");
                tokio::time::sleep(std::time::Duration::from_millis(
                    interval_ms,
                ))
                .await;
                cur_count += 1;
                continue;
            }
        } else {
            return Ok(());
        }
    }
    Ok(())
}

impl MergedNetworkState {
    fn verify(&self, current: &NetworkState) -> Result<(), NmstateError> {
        self.hostname.verify(current.hostname.as_ref())?;
        self.interfaces.verify(&current.interfaces)?;
        let ignored_kernel_ifaces: Vec<&str> = self
            .interfaces
            .ignored_ifaces
            .iter()
            .filter(|(_, t)| !t.is_userspace())
            .map(|(n, _)| n.as_str())
            .collect();
        self.routes.verify(
            &current.routes,
            ignored_kernel_ifaces.as_slice(),
            &current.interfaces,
        )?;
        self.rules
            .verify(&current.rules, ignored_kernel_ifaces.as_slice())?;
        self.dns.verify(current.dns.clone().unwrap_or_default())?;
        self.ovsdb
            .verify(current.ovsdb.clone().unwrap_or_default())?;
        self.ovn.verify(&current.ovn)?;
        Ok(())
    }
}

fn get_proper_verify_retry_count(merged_ifaces: &MergedInterfaces) -> usize {
    match merged_ifaces.get_sriov_vf_count() {
        0 => {
            if merged_ifaces.has_ovs() {
                VERIFY_RETRY_COUNT_OVS
            } else {
                VERIFY_RETRY_COUNT_DEFAULT
            }
        }
        v if v >= 64 => VERIFY_RETRY_COUNT_SRIOV_MAX,
        v if v <= 16 => VERIFY_RETRY_COUNT_SRIOV_MIN,
        v => v as usize * VERIFY_RETRY_COUNT_SRIOV_MAX / 64,
    }
}

#[cfg(test)]
mod tests {
    use std::{cell::Cell, time::Duration};

    use super::*;
    use crate::{Interfaces, unit_tests::testlib::new_eth_iface};

    fn run_checkpoint_test(test: impl Future<Output = ()>) {
        tokio::runtime::Builder::new_current_thread()
            .enable_time()
            .build()
            .unwrap()
            .block_on(test);
    }

    #[test]
    fn test_checkpoint_refresh_during_cleanup() {
        run_checkpoint_test(async {
            let refreshes = Cell::new(0);
            let starts = Cell::new(0);
            let completed = Cell::new(false);
            let (sender, receiver) = tokio::sync::oneshot::channel();
            let sender = Cell::new(Some(sender));

            with_checkpoint_refresh(
                async {
                    assert_eq!(refreshes.get(), 1);
                    starts.set(starts.get() + 1);
                    receiver.await.unwrap();
                    completed.set(true);
                    Ok(())
                },
                1,
                || async {
                    refreshes.set(refreshes.get() + 1);
                    if refreshes.get() == 3 {
                        sender.take().unwrap().send(()).unwrap();
                        tokio::time::sleep(Duration::from_millis(10)).await;
                        assert!(!completed.get());
                    }
                    Ok(())
                },
            )
            .await
            .unwrap();

            assert_eq!(refreshes.get(), 3);
            assert_eq!(starts.get(), 1);
            assert!(completed.get());
        });
    }

    #[test]
    fn test_checkpoint_refresh_failure_stops_cleanup() {
        run_checkpoint_test(async {
            for fail_on in [1, 2] {
                let refreshes = Cell::new(0);
                let started = Cell::new(false);
                let (sender, receiver) = tokio::sync::oneshot::channel::<()>();

                let error = with_checkpoint_refresh(
                    async {
                        let _sender = sender;
                        started.set(true);
                        std::future::pending().await
                    },
                    1,
                    || async {
                        refreshes.set(refreshes.get() + 1);
                        if refreshes.get() == fail_on {
                            Err(NmstateError::new(
                                ErrorKind::Bug,
                                "checkpoint lost".into(),
                            ))
                        } else {
                            Ok(())
                        }
                    },
                )
                .await
                .unwrap_err();

                assert_eq!(error.kind(), ErrorKind::Bug);
                assert_eq!(refreshes.get(), fail_on);
                assert_eq!(started.get(), fail_on == 2);
                assert!(receiver.await.is_err());
            }
        });
    }

    #[test]
    fn test_checkpoint_refresh_with_zero_timeout() {
        run_checkpoint_test(async {
            let refreshes = Cell::new(0);
            with_checkpoint_refresh(
                async {
                    assert_eq!(refreshes.get(), 1);
                    Ok(())
                },
                0,
                || async {
                    refreshes.set(refreshes.get() + 1);
                    Ok(())
                },
            )
            .await
            .unwrap();
            assert_eq!(refreshes.get(), 1);
        });
    }

    #[test]
    fn test_checkpoint_refresh_propagates_cleanup_failure() {
        run_checkpoint_test(async {
            let refreshes = Cell::new(0);
            let error = with_checkpoint_refresh(
                async {
                    Err(NmstateError::new(
                        ErrorKind::PluginFailure,
                        "rule update failed".into(),
                    ))
                },
                1,
                || async {
                    refreshes.set(refreshes.get() + 1);
                    Ok(())
                },
            )
            .await
            .unwrap_err();
            assert_eq!(error.kind(), ErrorKind::PluginFailure);
            assert_eq!(refreshes.get(), 1);
        });
    }

    fn merged_ifaces_with_vf_count(vfs: u32) -> MergedInterfaces {
        let desired = serde_yaml::from_str::<Interfaces>(&format!(
            r"---
- name: eth1
  type: ethernet
  state: up
  ethernet:
    sr-iov:
      total-vfs: {vfs}
"
        ))
        .unwrap();
        let mut current = Interfaces::new();
        current.push(new_eth_iface("eth1"));
        MergedInterfaces::new(desired, current, Default::default(), false)
            .unwrap()
    }

    #[test]
    fn test_verify_retry_count_scales_with_vf_count() {
        for (vfs, expected) in [
            (0, VERIFY_RETRY_COUNT_DEFAULT),
            (1, VERIFY_RETRY_COUNT_SRIOV_MIN),
            (16, VERIFY_RETRY_COUNT_SRIOV_MIN),
            (17, 79),
            (32, 150),
            (63, 295),
            (64, VERIFY_RETRY_COUNT_SRIOV_MAX),
            (128, VERIFY_RETRY_COUNT_SRIOV_MAX),
        ] {
            let count = get_proper_verify_retry_count(
                &merged_ifaces_with_vf_count(vfs),
            );
            assert_eq!(count, expected, "vf count {vfs}");
        }
    }
}
