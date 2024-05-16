// SPDX-License-Identifier: Apache-2.0

use crate::{
    nispor::{nispor_apply, nispor_retrieve, set_running_hostname},
    nm::{
        nm_apply, nm_checkpoint_create, nm_checkpoint_destroy,
        nm_checkpoint_rollback, nm_checkpoint_timeout_extend, nm_retrieve,
    },
    ovsdb::{
        ovsdb_apply, ovsdb_is_running, ovsdb_retrieve,
        DEFAULT_OVS_DB_SOCKET_PATH,
    },
    ErrorKind, MergedInterfaces, MergedNetworkState, NetworkState,
    NmstateError,
};

const DEFAULT_ROLLBACK_TIMEOUT: u32 = 60;
const VERIFY_RETRY_INTERVAL_MILLISECONDS: u64 = 1000;
const VERIFY_RETRY_COUNT_DEFAULT: usize = 5;
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
        nm_checkpoint_rollback(checkpoint)
    }

    /// Commit a checkpoint.
    /// Not available for `kernel only` mode.
    /// Only available for feature `query_apply`.
    pub fn checkpoint_commit(checkpoint: &str) -> Result<(), NmstateError> {
        nm_checkpoint_destroy(checkpoint)
    }

    /// Retrieve the `NetworkState`.
    /// Only available for feature `query_apply`.
    pub fn retrieve(&mut self) -> Result<&mut Self, NmstateError> {
        let state = nispor_retrieve(self.running_config_only)?;
        self.hostname = state.hostname;
        self.interfaces = state.interfaces;
        self.routes = state.routes;
        self.rules = state.rules;
        if ovsdb_is_running() {
            match ovsdb_retrieve() {
                Ok(mut ovsdb_state) => {
                    ovsdb_state.isolate_ovn()?;
                    self.update_state(&ovsdb_state);
                }
                Err(e) => {
                    log::warn!("Failed to retrieve OVS DB state: {}", e);
                }
            }
        }
        if !self.kernel_only {
            let nm_state = nm_retrieve(self.running_config_only)?;
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

        Ok(self)
    }

    /// Apply the `NetworkState`.
    /// Only available for feature `query_apply`.
    pub fn apply(&self) -> Result<(), NmstateError> {
        if self.interfaces.kernel_ifaces.len()
            + self.interfaces.user_ifaces.len()
            >= MAX_SUPPORTED_INTERFACES
        {
            log::warn!(
                "Interfaces count exceeds the support limit {} in \
                desired state",
                MAX_SUPPORTED_INTERFACES,
            );
        }
        if self.interfaces.has_up_ovs_iface() && !ovsdb_is_running() {
            log::warn!(
                "Desired state contains OVS interfaces, but not able \
                to connect OVS daemon at socket {}",
                DEFAULT_OVS_DB_SOCKET_PATH
            );
        }

        if !self.kernel_only {
            self.apply_with_nm_backend()
        } else {
            // TODO: Need checkpoint for kernel only mode
            self.apply_without_nm_backend()
        }
    }

    fn apply_with_nm_backend(&self) -> Result<(), NmstateError> {
        let mut merged_state = None;
        let mut cur_net_state = NetworkState::new();
        cur_net_state.set_kernel_only(self.kernel_only);
        cur_net_state.set_include_secrets(true);
        if let Err(e) = cur_net_state.retrieve() {
            if e.kind().can_retry() {
                log::info!("Retrying on: {}", e);
                std::thread::sleep(std::time::Duration::from_millis(
                    RETRY_NM_INTERVAL_MILLISECONDS,
                ));
                cur_net_state.retrieve()?;
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
                false,
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

        let checkpoint = match nm_checkpoint_create(timeout) {
            Ok(c) => c,
            Err(e) => {
                if e.kind().can_retry() {
                    log::info!("Retrying on: {}", e);
                    std::thread::sleep(std::time::Duration::from_millis(
                        RETRY_NM_INTERVAL_MILLISECONDS,
                    ));
                    nm_checkpoint_create(timeout)?
                } else {
                    return Err(e);
                }
            }
        };

        log::info!("Created checkpoint {}", &checkpoint);

        with_nm_checkpoint(&checkpoint, self.no_commit, || {
            if let Some(pf_state) = pf_state {
                let pf_merged_state = MergedNetworkState::new(
                    pf_state,
                    cur_net_state.clone(),
                    false,
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
                )?;
                // Refresh current state
                cur_net_state.retrieve()?;
                merged_state = Some(MergedNetworkState::new(
                    self.clone(),
                    cur_net_state.clone(),
                    false,
                    self.memory_only,
                )?);
            }

            let merged_state = if let Some(merged_state) = merged_state {
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
                &merged_state,
                &cur_net_state,
                &checkpoint,
                verify_count,
                timeout,
            )
        })
    }

    fn apply_with_nm_backend_and_under_checkpoint(
        &self,
        merged_state: &MergedNetworkState,
        cur_net_state: &Self,
        checkpoint: &str,
        retry_count: usize,
        timeout: u32,
    ) -> Result<(), NmstateError> {
        // NM might have unknown race problem found by verify stage,
        // we try to apply the state again if so.
        with_retry(RETRY_NM_INTERVAL_MILLISECONDS, RETRY_NM_COUNT, || {
            nm_checkpoint_timeout_extend(checkpoint, timeout)?;
            nm_apply(merged_state, checkpoint, timeout)?;
            if merged_state.ovsdb.is_changed && ovsdb_is_running() {
                ovsdb_apply(merged_state)?;
            }
            if let Some(running_hostname) =
                self.hostname.as_ref().and_then(|c| c.running.as_ref())
            {
                set_running_hostname(running_hostname)?;
            }
            if !self.no_verify {
                with_retry(
                    VERIFY_RETRY_INTERVAL_MILLISECONDS,
                    retry_count,
                    || {
                        nm_checkpoint_timeout_extend(checkpoint, timeout)?;
                        let mut new_cur_net_state = cur_net_state.clone();
                        new_cur_net_state.set_include_secrets(true);
                        new_cur_net_state.retrieve()?;
                        merged_state.verify(&new_cur_net_state)
                    },
                )
            } else {
                Ok(())
            }
        })
    }

    fn apply_without_nm_backend(&self) -> Result<(), NmstateError> {
        let mut cur_net_state = NetworkState::new();
        cur_net_state.set_kernel_only(self.kernel_only);
        cur_net_state.set_include_secrets(true);
        cur_net_state.retrieve()?;

        let merged_state = MergedNetworkState::new(
            self.clone(),
            cur_net_state.clone(),
            false,
            self.memory_only,
        )?;

        nispor_apply(&merged_state)?;
        if let Some(running_hostname) =
            self.hostname.as_ref().and_then(|c| c.running.as_ref())
        {
            set_running_hostname(running_hostname)?;
        }
        if !self.no_verify {
            with_retry(
                VERIFY_RETRY_INTERVAL_MILLISECONDS,
                VERIFY_RETRY_COUNT_KERNEL_MODE,
                || {
                    let mut new_cur_net_state = cur_net_state.clone();
                    new_cur_net_state.retrieve()?;
                    merged_state.verify(&new_cur_net_state)
                },
            )
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
            false,
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

        if merged_state.ovsdb.is_changed() {
            ret.ovsdb.clone_from(&self.ovsdb);
        }

        if merged_state.ovn.is_changed() {
            ret.ovn = self.ovn.clone();
        }
        Ok(ret)
    }
}

fn with_nm_checkpoint<T>(
    checkpoint: &str,
    no_commit: bool,
    func: T,
) -> Result<(), NmstateError>
where
    T: FnOnce() -> Result<(), NmstateError>,
{
    match func() {
        Ok(()) => {
            if !no_commit {
                nm_checkpoint_destroy(checkpoint)?;

                log::info!("Destroyed checkpoint {}", checkpoint);
            } else {
                log::info!("Skipping commit for checkpoint {}", checkpoint);
            }
            Ok(())
        }
        Err(e) => {
            if let Err(e) = nm_checkpoint_rollback(checkpoint) {
                log::warn!("nm_checkpoint_rollback() failed: {}", e);
            }
            log::info!("Rollbacked to checkpoint {}", checkpoint);
            Err(e)
        }
    }
}

fn with_retry<T>(
    interval_ms: u64,
    count: usize,
    func: T,
) -> Result<(), NmstateError>
where
    T: FnOnce() -> Result<(), NmstateError> + Copy,
{
    let mut cur_count = 0usize;
    while cur_count < count {
        if let Err(e) = func() {
            if cur_count == count - 1 || !e.kind().can_retry() {
                if e.kind().can_ignore() {
                    return Ok(());
                } else {
                    return Err(e);
                }
            } else {
                log::info!("Retrying on: {}", e);
                std::thread::sleep(std::time::Duration::from_millis(
                    interval_ms,
                ));
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
            .as_slice()
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
        0 => VERIFY_RETRY_COUNT_DEFAULT,
        v if v >= 64 => VERIFY_RETRY_COUNT_SRIOV_MAX,
        v if v <= 16 => VERIFY_RETRY_COUNT_SRIOV_MIN,
        v => v as usize / 64 * VERIFY_RETRY_COUNT_SRIOV_MAX,
    }
}
