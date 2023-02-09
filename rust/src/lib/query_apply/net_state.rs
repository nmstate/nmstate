// SPDX-License-Identifier: Apache-2.0

use crate::{
    nispor::{nispor_apply, nispor_retrieve, set_running_hostname},
    nm::{
        nm_apply, nm_checkpoint_create, nm_checkpoint_destroy,
        nm_checkpoint_rollback, nm_checkpoint_timeout_extend, nm_retrieve,
    },
    ovsdb::{ovsdb_apply, ovsdb_is_running, ovsdb_retrieve},
    MergedNetworkState, NetworkState, NmstateError,
};

const DEFAULT_ROLLBACK_TIMEOUT: u32 = 60;
const VERIFY_RETRY_INTERVAL_MILLISECONDS: u64 = 1000;
const VERIFY_RETRY_COUNT: usize = 5;
const VERIFY_RETRY_COUNT_SRIOV: usize = 60;
const VERIFY_RETRY_COUNT_KERNEL_MODE: usize = 5;
const VERIFY_RETRY_NM: usize = 2;
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
        self.retrieve_full()?;
        self.interfaces.hide_controller_prop();
        Ok(self)
    }

    pub(crate) fn retrieve_full(&mut self) -> Result<&mut Self, NmstateError> {
        let state = nispor_retrieve(self.running_config_only)?;
        if state.prop_list.contains(&"hostname") {
            self.hostname = state.hostname;
        }
        if state.prop_list.contains(&"interfaces") {
            self.interfaces = state.interfaces;
        }
        if state.prop_list.contains(&"routes") {
            self.routes = state.routes;
        }
        if state.prop_list.contains(&"rules") {
            self.rules = state.rules;
        }
        if ovsdb_is_running() {
            match ovsdb_retrieve() {
                Ok(ovsdb_state) => self.update_state(&ovsdb_state),
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
        if !self.kernel_only {
            self.apply_with_nm_backend()
        } else {
            // TODO: Need checkpoint for kernel only mode
            self.apply_without_nm_backend()
        }
    }

    fn apply_with_nm_backend(&self) -> Result<(), NmstateError> {
        let mut cur_net_state = NetworkState::new();
        cur_net_state.set_kernel_only(self.kernel_only);
        cur_net_state.set_include_secrets(true);
        cur_net_state.retrieve_full()?;

        let mut desired_state = self.clone();

        // At this point, the `unknown` interface type is not resolved yet,
        // hence when user want single-transaction for SR-IOV, they need
        // define the interface type. It is overkill to do resolve at this
        // point for this corner use case.
        let pf_state = desired_state.isolate_sriov_conf_out();

        let timeout = self.timeout.unwrap_or(DEFAULT_ROLLBACK_TIMEOUT);
        let checkpoint = nm_checkpoint_create(timeout)?;
        log::info!("Created checkpoint {}", &checkpoint);

        with_nm_checkpoint(&checkpoint, self.no_commit, || {
            if let Some(pf_state) = pf_state {
                pf_state.interfaces.check_sriov_capability()?;
                let pf_merged_state = MergedNetworkState::new(
                    pf_state,
                    cur_net_state.clone(),
                    false,
                    self.memory_only,
                )?;
                self.apply_with_nm_backend_and_under_checkpoint(
                    &pf_merged_state,
                    &cur_net_state,
                    &checkpoint,
                    VERIFY_RETRY_COUNT_SRIOV,
                )?;
                // Refresh current state
                cur_net_state.retrieve_full()?;
            }

            let merged_state = MergedNetworkState::new(
                desired_state,
                cur_net_state.clone(),
                false,
                self.memory_only,
            )?;

            self.apply_with_nm_backend_and_under_checkpoint(
                &merged_state,
                &cur_net_state,
                &checkpoint,
                VERIFY_RETRY_COUNT,
            )
        })
    }

    fn apply_with_nm_backend_and_under_checkpoint(
        &self,
        merged_state: &MergedNetworkState,
        cur_net_state: &Self,
        checkpoint: &str,
        retry_count: usize,
    ) -> Result<(), NmstateError> {
        let timeout = self.timeout.unwrap_or(DEFAULT_ROLLBACK_TIMEOUT);
        // NM might have unknown race problem found by verify stage,
        // we try to apply the state again if so.
        with_retry(VERIFY_RETRY_INTERVAL_MILLISECONDS, VERIFY_RETRY_NM, || {
            nm_checkpoint_timeout_extend(checkpoint, timeout)?;
            nm_apply(merged_state, checkpoint, timeout)?;
            if merged_state.is_global_ovsdb_changed() && ovsdb_is_running() {
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
                        new_cur_net_state.retrieve_full()?;
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
        cur_net_state.retrieve_full()?;

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
                    new_cur_net_state.retrieve_full()?;
                    merged_state.verify(&new_cur_net_state)
                },
            )
        } else {
            Ok(())
        }
    }

    pub(crate) fn update_state(&mut self, other: &Self) {
        if other.prop_list.contains(&"hostname") {
            if let Some(h) = self.hostname.as_mut() {
                if let Some(other_h) = other.hostname.as_ref() {
                    h.update(other_h);
                }
            } else {
                self.hostname = other.hostname.clone();
            }
        }
        if other.prop_list.contains(&"interfaces") {
            self.interfaces.update(&other.interfaces);
        }
        if other.prop_list.contains(&"dns") {
            self.dns = other.dns.clone();
        }
        if other.prop_list.contains(&"ovsdb") {
            self.ovsdb = other.ovsdb.clone();
        }
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
                return Err(e);
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
        self.routes
            .verify(&current.routes, ignored_kernel_ifaces.as_slice())?;
        self.rules
            .verify(&current.rules, ignored_kernel_ifaces.as_slice())?;
        self.dns.verify(&current.dns)?;
        self.ovsdb.verify(&current.ovsdb)?;
        Ok(())
    }
}
