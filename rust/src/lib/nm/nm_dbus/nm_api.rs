// SPDX-License-Identifier: Apache-2.0

use std::convert::TryFrom;
use std::time::{Duration, Instant};

use log::debug;

use super::{
    active_connection::{
        get_nm_ac_by_obj_path, nm_ac_obj_path_uuid_get, NmActiveConnection,
    },
    connection::{nm_con_get_from_obj_path, NmConnection},
    dbus::NmDbus,
    device::{
        nm_dev_delete, nm_dev_from_obj_path, nm_dev_get_llpd, NmDevice,
        NmDeviceState, NmDeviceStateReason,
    },
    dns::{NmDnsEntry, NmGlobalDnsConfig},
    error::{ErrorKind, NmError},
    lldp::NmLldpNeighbor,
};

pub struct NmApi<'a> {
    pub(crate) dbus: NmDbus<'a>,
    checkpoint: Option<String>,
    cp_refresh_time: Option<std::time::Instant>,
    cp_timeout: u32,
    auto_cp_refresh: bool,
}

impl<'a> NmApi<'a> {
    pub fn new() -> Result<Self, NmError> {
        Ok(Self {
            dbus: NmDbus::new()?,
            checkpoint: None,
            cp_refresh_time: None,
            cp_timeout: 0,
            auto_cp_refresh: false,
        })
    }

    pub fn set_checkpoint(&mut self, checkpoint: &str, timeout: u32) {
        self.checkpoint = Some(checkpoint.to_string());
        self.cp_timeout = timeout;
        self.cp_refresh_time = Some(std::time::Instant::now());
    }

    pub fn set_checkpoint_auto_refresh(&mut self, value: bool) {
        self.auto_cp_refresh = value;
    }

    pub fn version(&self) -> Result<String, NmError> {
        self.dbus.version()
    }

    pub fn checkpoint_create(
        &mut self,
        timeout: u32,
    ) -> Result<String, NmError> {
        debug!("checkpoint_create");
        let cp = self.dbus.checkpoint_create(timeout)?;
        debug!("checkpoint created: {}", &cp);
        self.checkpoint = Some(cp.clone());
        self.cp_refresh_time = Some(std::time::Instant::now());
        self.cp_timeout = timeout;
        Ok(cp)
    }

    pub fn checkpoint_destroy(
        &mut self,
        checkpoint: &str,
    ) -> Result<(), NmError> {
        let mut checkpoint_to_destroy: String = checkpoint.to_string();
        if checkpoint_to_destroy.is_empty() {
            checkpoint_to_destroy = self.last_active_checkpoint()?
        }
        self.checkpoint = None;
        self.cp_refresh_time = None;
        debug!("checkpoint_destroy: {}", checkpoint_to_destroy);
        self.dbus.checkpoint_destroy(checkpoint_to_destroy.as_str())
    }

    pub fn checkpoint_rollback(
        &mut self,
        checkpoint: &str,
    ) -> Result<(), NmError> {
        let mut checkpoint_to_rollback: String = checkpoint.to_string();
        if checkpoint_to_rollback.is_empty() {
            checkpoint_to_rollback = self.last_active_checkpoint()?
        }
        self.checkpoint = None;
        self.cp_refresh_time = None;
        debug!("checkpoint_rollback: {}", checkpoint_to_rollback);
        self.dbus
            .checkpoint_rollback(checkpoint_to_rollback.as_str())
    }

    fn last_active_checkpoint(&self) -> Result<String, NmError> {
        debug!("last_active_checkpoint");
        let mut checkpoints = self.dbus.checkpoints()?;
        if !checkpoints.is_empty() {
            Ok(checkpoints.remove(0))
        } else {
            Err(NmError::new(
                ErrorKind::NotFound,
                "Not active checkpoints".to_string(),
            ))
        }
    }

    pub fn connection_activate(&mut self, uuid: &str) -> Result<(), NmError> {
        debug!("connection_activate: {}", uuid);
        self.extend_timeout_if_required()?;
        let nm_conn = self.dbus.get_conn_obj_path_by_uuid(uuid)?;
        self.dbus.connection_activate(&nm_conn)
    }

    pub fn connection_deactivate(&mut self, uuid: &str) -> Result<(), NmError> {
        debug!("connection_deactivate: {}", uuid);
        self.extend_timeout_if_required()?;
        if let Ok(nm_ac) = get_nm_ac_obj_path_by_uuid(&self.dbus, uuid) {
            if !nm_ac.is_empty() {
                self.dbus.connection_deactivate(&nm_ac)?;
            }
        }
        Ok(())
    }

    pub fn connections_get(&mut self) -> Result<Vec<NmConnection>, NmError> {
        debug!("connections_get");
        self.extend_timeout_if_required()?;
        let mut nm_conns = Vec::new();
        for nm_conn_obj_path in self.dbus.nm_conn_obj_paths_get()? {
            // Race: Connection might just been deleted, hence we ignore error
            // here
            if let Ok(c) = nm_con_get_from_obj_path(
                &self.dbus.connection,
                &nm_conn_obj_path,
            ) {
                nm_conns.push(c);
            }
        }
        Ok(nm_conns)
    }

    pub fn applied_connections_get(
        &mut self,
    ) -> Result<Vec<NmConnection>, NmError> {
        debug!("applied_connections_get");
        self.extend_timeout_if_required()?;
        let nm_dev_obj_paths = self.dbus.nm_dev_obj_paths_get()?;
        let mut nm_conns: Vec<NmConnection> = Vec::new();
        for nm_dev_obj_path in nm_dev_obj_paths {
            self.extend_timeout_if_required()?;
            match self.dbus.nm_dev_applied_connection_get(&nm_dev_obj_path) {
                Ok(nm_conn) => nm_conns.push(nm_conn),
                Err(e) => {
                    debug!(
                        "Ignoring error when get applied connection for \
                        dev {}: {}",
                        nm_dev_obj_path, e
                    );
                }
            }
        }
        Ok(nm_conns)
    }

    pub fn connection_add(
        &mut self,
        nm_conn: &NmConnection,
        memory_only: bool,
    ) -> Result<(), NmError> {
        debug!("connection_add: {:?}", nm_conn);
        self.extend_timeout_if_required()?;
        if !nm_conn.obj_path.is_empty() {
            self.dbus.connection_update(
                nm_conn.obj_path.as_str(),
                nm_conn,
                memory_only,
            )
        } else {
            self.dbus.connection_add(nm_conn, memory_only)
        }
    }

    pub fn connection_delete(&mut self, uuid: &str) -> Result<(), NmError> {
        debug!("connection_delete: {}", uuid);
        self.extend_timeout_if_required()?;
        if let Ok(con_obj_path) = self.dbus.get_conn_obj_path_by_uuid(uuid) {
            debug!("Found nm_connection {} for UUID {}", con_obj_path, uuid);
            if !con_obj_path.is_empty() {
                self.dbus.connection_delete(&con_obj_path)?;
            }
        }
        Ok(())
    }

    pub fn connection_reapply(
        &mut self,
        nm_conn: &NmConnection,
    ) -> Result<(), NmError> {
        debug!("connection_reapply: {:?}", nm_conn);
        self.extend_timeout_if_required()?;
        if let Some(iface_name) = nm_conn.iface_name() {
            let nm_dev_obj_path = self.dbus.nm_dev_obj_path_get(iface_name)?;
            self.dbus.nm_dev_reapply(&nm_dev_obj_path, nm_conn)
        } else {
            Err(NmError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Failed to extract interface name from connection {nm_conn:?}"
                ),
            ))
        }
    }

    pub fn active_connections_get(
        &mut self,
    ) -> Result<Vec<NmActiveConnection>, NmError> {
        debug!("active_connections_get");
        self.extend_timeout_if_required()?;
        let mut nm_acs = Vec::new();
        let nm_ac_obj_paths = self.dbus.active_connections()?;
        for nm_ac_obj_path in nm_ac_obj_paths {
            // Race condition: Active connection might just been deleted,
            // we ignore error here
            if let Ok(Some(nm_ac)) =
                get_nm_ac_by_obj_path(&self.dbus.connection, &nm_ac_obj_path)
            {
                debug!("Got active connection {:?}", nm_ac);
                nm_acs.push(nm_ac);
            }
        }
        Ok(nm_acs)
    }

    pub fn checkpoint_timeout_extend(
        &self,
        checkpoint: &str,
        added_time_sec: u32,
    ) -> Result<(), NmError> {
        debug!(
            "checkpoint_timeout_extend: {} {}",
            checkpoint, added_time_sec
        );
        self.dbus
            .checkpoint_timeout_extend(checkpoint, added_time_sec)
    }

    pub fn devices_get(&mut self) -> Result<Vec<NmDevice>, NmError> {
        debug!("devices_get");
        self.extend_timeout_if_required()?;
        let mut ret = Vec::new();
        for nm_dev_obj_path in &self.dbus.nm_dev_obj_paths_get()? {
            match nm_dev_from_obj_path(&self.dbus.connection, nm_dev_obj_path) {
                Ok(nm_dev) => {
                    debug!("Got Device {:?}", nm_dev);
                    ret.push(nm_dev);
                }
                Err(e) => {
                    // We might have race when relieve device list along with
                    // deleting device
                    debug!(
                        "Failed to retrieve device {} {}",
                        nm_dev_obj_path, e
                    )
                }
            }
        }
        Ok(ret)
    }

    pub fn device_delete(
        &mut self,
        nm_dev_obj_path: &str,
    ) -> Result<(), NmError> {
        self.extend_timeout_if_required()?;
        nm_dev_delete(&self.dbus.connection, nm_dev_obj_path)
    }

    pub fn device_lldp_neighbor_get(
        &mut self,
        nm_dev_obj_path: &str,
    ) -> Result<Vec<NmLldpNeighbor>, NmError> {
        self.extend_timeout_if_required()?;
        nm_dev_get_llpd(&self.dbus.connection, nm_dev_obj_path)
    }

    // If any device is with NewActivation or IpConfig state,
    // we wait its activation.
    pub fn wait_checkpoint_rollback(
        &mut self,
        // TODO: return error when waiting_nm_dev is not changing for given
        // time.
        timeout: u32,
    ) -> Result<(), NmError> {
        debug!("wait_checkpoint_rollback");
        let start = Instant::now();
        while start.elapsed() <= Duration::from_secs(timeout.into()) {
            let mut waiting_nm_dev: Vec<&NmDevice> = Vec::new();
            let nm_devs = self.devices_get()?;
            for nm_dev in &nm_devs {
                if nm_dev.state_reason == NmDeviceStateReason::NewActivation
                    || nm_dev.state == NmDeviceState::IpConfig
                    || nm_dev.state == NmDeviceState::Deactivating
                {
                    waiting_nm_dev.push(nm_dev);
                }
            }
            if waiting_nm_dev.is_empty() {
                return Ok(());
            } else {
                debug!(
                    "Waiting rollback on these devices {:?}",
                    waiting_nm_dev
                );
                std::thread::sleep(Duration::from_millis(500));
            }
        }
        Err(NmError::new(
            ErrorKind::Timeout,
            "Timeout on waiting rollback".to_string(),
        ))
    }

    pub fn get_dns_configuration(
        &mut self,
    ) -> Result<Vec<NmDnsEntry>, NmError> {
        let mut ret: Vec<NmDnsEntry> = Vec::new();
        self.extend_timeout_if_required()?;
        for dns_value in self.dbus.get_dns_configuration()? {
            ret.push(NmDnsEntry::try_from(dns_value)?);
        }
        Ok(ret)
    }

    pub fn hostname_set(&mut self, hostname: &str) -> Result<(), NmError> {
        self.extend_timeout_if_required()?;
        if hostname.is_empty() {
            // Due to bug https://bugzilla.redhat.com/2090946
            // NetworkManager daemon cannot remove static hostname, hence we
            // just delete the /etc/hostname file
            if std::path::Path::new("/etc/hostname").exists() {
                if let Err(e) = std::fs::remove_file("/etc/hostname") {
                    log::error!("Failed to remove static /etc/hostname: {}", e);
                }
            }
            Ok(())
        } else {
            self.dbus.hostname_set(hostname)
        }
    }

    pub fn extend_timeout_if_required(&mut self) -> Result<(), NmError> {
        if let (Some(cp_refresh_time), Some(checkpoint)) =
            (self.cp_refresh_time.as_ref(), self.checkpoint.as_ref())
        {
            // Only extend the timeout when only half of it elapsed
            if self.auto_cp_refresh
                && cp_refresh_time.elapsed().as_secs()
                    >= self.cp_timeout as u64 / 2
            {
                log::debug!("Extending checkpoint timeout");
                self.checkpoint_timeout_extend(checkpoint, self.cp_timeout)?;
                self.cp_refresh_time = Some(Instant::now());
            }
        }
        Ok(())
    }

    pub fn get_global_dns_configuration(
        &self,
    ) -> Result<NmGlobalDnsConfig, NmError> {
        NmGlobalDnsConfig::try_from(self.dbus.global_dns_configuration()?)
    }

    pub fn set_global_dns_configuration(
        &mut self,
        config: &NmGlobalDnsConfig,
    ) -> Result<(), NmError> {
        self.extend_timeout_if_required()?;
        self.dbus.set_global_dns_configuration(config.to_value()?)
    }
}

fn get_nm_ac_obj_path_by_uuid(
    dbus: &NmDbus,
    uuid: &str,
) -> Result<String, NmError> {
    let nm_ac_obj_paths = dbus.active_connections()?;

    for nm_ac_obj_path in nm_ac_obj_paths {
        if nm_ac_obj_path_uuid_get(&dbus.connection, &nm_ac_obj_path)? == uuid {
            return Ok(nm_ac_obj_path);
        }
    }
    Ok("".into())
}
