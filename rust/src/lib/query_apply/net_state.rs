// SPDX-License-Identifier: Apache-2.0

use crate::{
    nispor::{nispor_apply, nispor_retrieve, set_running_hostname},
    nm::{
        nm_apply, nm_checkpoint_create, nm_checkpoint_destroy,
        nm_checkpoint_rollback, nm_checkpoint_timeout_extend, nm_retrieve,
    },
    ovsdb::{ovsdb_apply, ovsdb_is_running, ovsdb_retrieve},
    query_apply::get_ignored_ifaces,
    NetworkState, NmstateError,
};

const DEFAULT_ROLLBACK_TIMEOUT: u32 = 60;
const VERIFY_RETRY_INTERVAL_MILLISECONDS: u64 = 1000;
const VERIFY_RETRY_COUNT: usize = 5;
const VERIFY_RETRY_COUNT_SRIOV: usize = 60;
const VERIFY_RETRY_COUNT_KERNEL_MODE: usize = 5;
const VERIFY_RETRY_NM: usize = 2;
const MAX_SUPPORTED_INTERFACES: usize = 1000;

impl NetworkState {
    pub fn checkpoint_rollback(checkpoint: &str) -> Result<(), NmstateError> {
        nm_checkpoint_rollback(checkpoint)
    }

    pub fn checkpoint_commit(checkpoint: &str) -> Result<(), NmstateError> {
        nm_checkpoint_destroy(checkpoint)
    }

    pub fn retrieve(&mut self) -> Result<&mut Self, NmstateError> {
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
        if !self.kernel_only {
            let nm_state = nm_retrieve(self.running_config_only)?;
            // TODO: Priority handling
            self.update_state(&nm_state);
            if ovsdb_is_running() {
                match ovsdb_retrieve() {
                    Ok(ovsdb_state) => self.update_state(&ovsdb_state),
                    Err(e) => {
                        log::warn!("Failed to retrieve OVS DB state: {}", e);
                    }
                }
            }
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

    pub fn apply(&self) -> Result<(), NmstateError> {
        let mut desire_state_to_verify = self.clone();
        let mut desire_state_to_apply = self.clone();
        let mut cur_net_state = NetworkState::new();
        cur_net_state.set_kernel_only(self.kernel_only);
        cur_net_state.set_include_secrets(true);
        cur_net_state.retrieve()?;

        if desire_state_to_apply.interfaces.to_vec().len()
            >= MAX_SUPPORTED_INTERFACES
        {
            log::warn!(
                "Interfaces count exceeds the support limit {} in \
                desired state",
                MAX_SUPPORTED_INTERFACES,
            );
        }

        let (ignored_kernel_ifaces, ignored_user_ifaces) =
            get_ignored_ifaces(&self.interfaces, &cur_net_state.interfaces);

        for iface_name in &ignored_kernel_ifaces {
            log::info!("Ignoring kernel interface {}", iface_name)
        }
        for (iface_name, iface_type) in &ignored_user_ifaces {
            log::info!(
                "Ignoring user space interface {} with type {}",
                iface_name,
                iface_type
            )
        }

        desire_state_to_apply.interfaces.pre_ignore_check(
            &cur_net_state.interfaces,
            &ignored_kernel_ifaces,
        )?;

        desire_state_to_apply.interfaces.remove_ignored_ifaces(
            &ignored_kernel_ifaces,
            &ignored_user_ifaces,
        );
        cur_net_state.interfaces.remove_ignored_ifaces(
            &ignored_kernel_ifaces,
            &ignored_user_ifaces,
        );

        desire_state_to_apply
            .routes
            .remove_ignored_iface_routes(ignored_kernel_ifaces.as_slice());
        cur_net_state
            .routes
            .remove_ignored_iface_routes(ignored_kernel_ifaces.as_slice());

        desire_state_to_verify
            .interfaces
            .resolve_unknown_ifaces(&cur_net_state.interfaces)?;
        desire_state_to_apply
            .interfaces
            .resolve_unknown_ifaces(&cur_net_state.interfaces)?;

        desire_state_to_apply
            .interfaces
            .resolve_sriov_reference(&cur_net_state.interfaces)?;

        let (add_net_state, chg_net_state, del_net_state) =
            desire_state_to_apply.gen_state_for_apply(&cur_net_state)?;

        log::debug!("Adding net state {:?}", &add_net_state);
        log::debug!("Changing net state {:?}", &chg_net_state);
        log::debug!("Deleting net state {:?}", &del_net_state);

        if !self.kernel_only {
            let retry_count =
                if desire_state_to_apply.interfaces.has_sriov_enabled() {
                    VERIFY_RETRY_COUNT_SRIOV
                } else {
                    VERIFY_RETRY_COUNT
                };

            let timeout = self.timeout.unwrap_or(DEFAULT_ROLLBACK_TIMEOUT);
            let checkpoint = nm_checkpoint_create(timeout)?;
            log::info!("Created checkpoint {}", &checkpoint);

            with_nm_checkpoint(&checkpoint, self.no_commit, || {
                // NM might have unknown race problem found by verify stage,
                // we try to apply the state again if so.
                with_retry(
                    VERIFY_RETRY_INTERVAL_MILLISECONDS,
                    VERIFY_RETRY_NM,
                    || {
                        nm_apply(
                            &add_net_state,
                            &chg_net_state,
                            &del_net_state,
                            // TODO: Passing full(desire + current) network
                            // state instead of
                            // current,
                            &cur_net_state,
                            &desire_state_to_apply,
                            &checkpoint,
                            self.memory_only,
                        )?;
                        if desire_state_to_apply.prop_list.contains(&"ovsdb")
                            && ovsdb_is_running()
                        {
                            ovsdb_apply(
                                &desire_state_to_apply,
                                &cur_net_state,
                            )?;
                        }
                        if let Some(running_hostname) = self
                            .hostname
                            .as_ref()
                            .and_then(|c| c.running.as_ref())
                        {
                            set_running_hostname(running_hostname)?;
                        }
                        if !self.no_verify {
                            with_retry(
                                VERIFY_RETRY_INTERVAL_MILLISECONDS,
                                retry_count,
                                || {
                                    nm_checkpoint_timeout_extend(
                                        &checkpoint,
                                        timeout,
                                    )?;
                                    let mut new_cur_net_state =
                                        cur_net_state.clone();
                                    new_cur_net_state.set_include_secrets(true);
                                    new_cur_net_state.retrieve()?;
                                    desire_state_to_verify.verify(
                                        &cur_net_state,
                                        &new_cur_net_state,
                                    )
                                },
                            )
                        } else {
                            Ok(())
                        }
                    },
                )
            })
        } else {
            // TODO: Need checkpoint for kernel only mode
            nispor_apply(
                &add_net_state,
                &chg_net_state,
                &del_net_state,
                &cur_net_state,
            )?;
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
                        desire_state_to_verify
                            .verify(&cur_net_state, &new_cur_net_state)
                    },
                )
            } else {
                Ok(())
            }
        }
    }

    fn verify(
        &self,
        pre_apply_current: &Self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        if let Some(desired_hostname) = self.hostname.as_ref() {
            desired_hostname.verify(current.hostname.as_ref())?;
        }
        self.interfaces
            .verify(&pre_apply_current.interfaces, &current.interfaces)?;
        let (ignored_kernel_ifaces, _) =
            get_ignored_ifaces(&self.interfaces, &current.interfaces);
        self.routes
            .verify(&current.routes, &ignored_kernel_ifaces)?;
        self.rules.verify(&current.rules)?;
        self.dns.verify(&current.dns)?;
        self.ovsdb.verify(&current.ovsdb)
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
            if cur_count == count - 1 {
                return Err(e);
            } else {
                log::info!("Retrying on verification failure: {}", e);
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
