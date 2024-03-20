// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use log::debug;

use super::{
    connection::{NmConnection, NmConnectionDbusValue},
    dbus_proxy::{
        NetworkManagerDnsProxy, NetworkManagerProxy, NetworkManagerSettingProxy,
    },
    error::{ErrorKind, NmError},
};

const NM_CHECKPOINT_CREATE_FLAG_DELETE_NEW_CONNECTIONS: u32 = 0x02;
const NM_CHECKPOINT_CREATE_FLAG_DISCONNECT_NEW_DEVICES: u32 = 0x04;
const NM_CHECKPOINT_CREATE_FLAG_TRACK_INTERNAL_GLOBAL_DNS: u32 = 0x20;

const OBJ_PATH_NULL_STR: &str = "/";

pub(crate) const NM_DBUS_INTERFACE_ROOT: &str =
    "org.freedesktop.NetworkManager";
pub(crate) const NM_DBUS_INTERFACE_SETTING: &str =
    "org.freedesktop.NetworkManager.Settings.Connection";
pub(crate) const NM_DBUS_INTERFACE_AC: &str =
    "org.freedesktop.NetworkManager.Connection.Active";
pub(crate) const NM_DBUS_INTERFACE_DEV: &str =
    "org.freedesktop.NetworkManager.Device";

const NM_DBUS_INTERFACE_DEVICE: &str = "org.freedesktop.NetworkManager.Device";

const NM_SETTINGS_CREATE2_FLAGS_TO_DISK: u32 = 1;
const NM_SETTINGS_CREATE2_FLAGS_IN_MEMORY: u32 = 2;
const NM_SETTINGS_CREATE2_FLAGS_BLOCK_AUTOCONNECT: u32 = 32;

const NM_SETTINGS_UPDATE2_FLAGS_TO_DISK: u32 = 1;
const NM_SETTINGS_UPDATE2_FLAGS_IN_MEMORY: u32 = 2;
const NM_SETTINGS_UPDATE2_FLAGS_BLOCK_AUTOCONNECT: u32 = 32;

pub(crate) struct NmDbus<'a> {
    pub(crate) connection: zbus::Connection,
    proxy: NetworkManagerProxy<'a>,
    setting_proxy: NetworkManagerSettingProxy<'a>,
    dns_proxy: NetworkManagerDnsProxy<'a>,
}

impl<'a> NmDbus<'a> {
    pub(crate) fn new() -> Result<Self, NmError> {
        let connection = zbus::Connection::new_system()?;
        let proxy = NetworkManagerProxy::new(&connection)?;
        let setting_proxy = NetworkManagerSettingProxy::new(&connection)?;
        let dns_proxy = NetworkManagerDnsProxy::new(&connection)?;

        Ok(Self {
            connection,
            proxy,
            setting_proxy,
            dns_proxy,
        })
    }

    pub(crate) fn version(&self) -> Result<String, NmError> {
        Ok(self.proxy.version()?)
    }

    fn _checkpoint_create(
        &self,
        timeout: u32,
        flags: u32,
    ) -> Result<String, NmError> {
        match self.proxy.checkpoint_create(&[], timeout, flags) {
            Ok(cp) => Ok(obj_path_to_string(cp)),
            Err(e) => {
                Err(if let zbus::Error::MethodError(ref error_type, ..) = e {
                    if error_type
                        == "org.freedesktop.NetworkManager.InvalidArguments"
                    {
                        NmError::new(
                            ErrorKind::CheckpointConflict,
                            "Another checkpoint exists, \
                            please wait its timeout or destroy it"
                                .to_string(),
                        )
                    } else {
                        e.into()
                    }
                } else {
                    e.into()
                })
            }
        }
    }

    pub(crate) fn checkpoint_create(
        &self,
        timeout: u32,
    ) -> Result<String, NmError> {
        let default_flags = NM_CHECKPOINT_CREATE_FLAG_DELETE_NEW_CONNECTIONS
            | NM_CHECKPOINT_CREATE_FLAG_DISCONNECT_NEW_DEVICES;
        match self._checkpoint_create(
            timeout,
            default_flags | NM_CHECKPOINT_CREATE_FLAG_TRACK_INTERNAL_GLOBAL_DNS,
        ) {
            Ok(s) => Ok(s),
            Err(_) => {
                // The NM_CHECKPOINT_CREATE_FLAG_TRACK_INTERNAL_GLOBAL_DNS is
                // supported by NM 1.47+ and might be backported to other
                // versions. There is no way to know whether it is supported or
                // not by checking the NM version. Hence we try to create
                // the checkpoint without this flag on second try.
                self._checkpoint_create(timeout, default_flags)
            }
        }
    }

    pub(crate) fn checkpoint_destroy(
        &self,
        checkpoint: &str,
    ) -> Result<(), NmError> {
        debug!("checkpoint_destroy: {}", checkpoint);
        Ok(self
            .proxy
            .checkpoint_destroy(&str_to_obj_path(checkpoint)?)?)
    }

    pub(crate) fn checkpoint_rollback(
        &self,
        checkpoint: &str,
    ) -> Result<(), NmError> {
        debug!("checkpoint_rollback: {}", checkpoint);
        self.proxy
            .checkpoint_rollback(&str_to_obj_path(checkpoint)?)?;
        Ok(())
    }

    pub(crate) fn checkpoints(&self) -> Result<Vec<String>, NmError> {
        Ok(self
            .proxy
            .checkpoints()?
            .into_iter()
            .map(obj_path_to_string)
            .collect())
    }

    pub(crate) fn get_conn_obj_path_by_uuid(
        &self,
        uuid: &str,
    ) -> Result<String, NmError> {
        match self.setting_proxy.get_connection_by_uuid(uuid) {
            Ok(c) => Ok(obj_path_to_string(c)),
            Err(e) => {
                if let zbus::Error::MethodError(ref error_type, ..) = e {
                    if error_type
                        == &format!(
                            "{NM_DBUS_INTERFACE_ROOT}.Settings.InvalidConnection",
                        )
                    {
                        Err(NmError::new(
                            ErrorKind::NotFound,
                            format!("Connection with UUID {uuid} not found"),
                        ))
                    } else {
                        Err(e.into())
                    }
                } else {
                    Err(e.into())
                }
            }
        }
    }

    pub(crate) fn connection_activate(
        &self,
        nm_conn: &str,
    ) -> Result<(), NmError> {
        self.proxy.activate_connection(
            &str_to_obj_path(nm_conn)?,
            &str_to_obj_path(OBJ_PATH_NULL_STR)?,
            &str_to_obj_path(OBJ_PATH_NULL_STR)?,
        )?;
        Ok(())
    }

    pub(crate) fn active_connections(&self) -> Result<Vec<String>, NmError> {
        Ok(self
            .proxy
            .active_connections()?
            .into_iter()
            .map(obj_path_to_string)
            .collect())
    }

    pub(crate) fn connection_deactivate(
        &self,
        nm_ac: &str,
    ) -> Result<(), NmError> {
        Ok(self.proxy.deactivate_connection(&str_to_obj_path(nm_ac)?)?)
    }

    pub(crate) fn connection_add(
        &self,
        nm_conn: &NmConnection,
        memory_only: bool,
    ) -> Result<(), NmError> {
        let value = nm_conn.to_value()?;
        let flags = NM_SETTINGS_CREATE2_FLAGS_BLOCK_AUTOCONNECT
            + if memory_only {
                NM_SETTINGS_CREATE2_FLAGS_IN_MEMORY
            } else {
                NM_SETTINGS_CREATE2_FLAGS_TO_DISK
            };
        self.setting_proxy
            .add_connection2(value, flags, HashMap::new())?;
        Ok(())
    }

    pub(crate) fn connection_delete(
        &self,
        con_obj_path: &str,
    ) -> Result<(), NmError> {
        debug!("connection_delete: {}", con_obj_path);
        let proxy = zbus::Proxy::new(
            &self.connection,
            NM_DBUS_INTERFACE_ROOT,
            con_obj_path,
            NM_DBUS_INTERFACE_SETTING,
        )?;
        Ok(proxy.call::<(), ()>("Delete", &())?)
    }

    pub(crate) fn connection_update(
        &self,
        con_obj_path: &str,
        nm_conn: &NmConnection,
        memory_only: bool,
    ) -> Result<(), NmError> {
        let value = nm_conn.to_value()?;
        let proxy = zbus::Proxy::new(
            &self.connection,
            NM_DBUS_INTERFACE_ROOT,
            con_obj_path,
            NM_DBUS_INTERFACE_SETTING,
        )?;
        let flags = NM_SETTINGS_UPDATE2_FLAGS_BLOCK_AUTOCONNECT
            + if memory_only {
                NM_SETTINGS_UPDATE2_FLAGS_IN_MEMORY
            } else {
                NM_SETTINGS_UPDATE2_FLAGS_TO_DISK
            };
        proxy.call::<(
                NmConnectionDbusValue,
                u32,
                HashMap<&str, zvariant::Value>,
            ), HashMap<String, zvariant::OwnedValue>>(
                "Update2",
                &(
                    value,
                    flags,
                    HashMap::new()
                ),
            )?;
        Ok(())
    }

    pub(crate) fn nm_dev_obj_path_get(
        &self,
        iface_name: &str,
    ) -> Result<String, NmError> {
        Ok(obj_path_to_string(
            self.proxy.get_device_by_ip_iface(iface_name)?,
        ))
    }

    pub(crate) fn nm_dev_obj_paths_get(&self) -> Result<Vec<String>, NmError> {
        Ok(self
            .proxy
            .get_all_devices()?
            .into_iter()
            .map(obj_path_to_string)
            .collect())
    }

    pub(crate) fn nm_dev_applied_connection_get(
        &self,
        nm_dev_obj_path: &str,
    ) -> Result<NmConnection, NmError> {
        let proxy = zbus::Proxy::new(
            &self.connection,
            NM_DBUS_INTERFACE_ROOT,
            nm_dev_obj_path,
            NM_DBUS_INTERFACE_DEVICE,
        )?;
        let (nm_conn, _) = proxy.call::<u32, (NmConnection, u64)>(
            "GetAppliedConnection",
            &(
                0
                // NM document require it to be zero
            ),
        )?;
        Ok(nm_conn)
    }

    pub(crate) fn nm_dev_reapply(
        &self,
        nm_dev_obj_path: &str,
        nm_conn: &NmConnection,
    ) -> Result<(), NmError> {
        let value = nm_conn.to_value()?;
        let proxy = zbus::Proxy::new(
            &self.connection,
            NM_DBUS_INTERFACE_ROOT,
            nm_dev_obj_path,
            NM_DBUS_INTERFACE_DEVICE,
        )?;
        match proxy.call::<(NmConnectionDbusValue, u64, u32), ()>(
            "Reapply",
            &(
                value, 0, /* ignore version id */
                0, /* flag, NM document require always be zero */
            ),
        ) {
            Ok(()) => Ok(()),
            Err(e) => {
                if let zbus::Error::MethodError(
                    ref error_type,
                    Some(ref err_msg),
                    ..,
                ) = e
                {
                    if error_type
                        == &format!(
                            "{NM_DBUS_INTERFACE_ROOT}.Device.IncompatibleConnection"
                        )
                    {
                        Err(NmError::new(
                            ErrorKind::IncompatibleReapply,
                            err_msg.to_string(),
                        ))
                    } else {
                        Err(e.into())
                    }
                } else {
                    Err(e.into())
                }
            }
        }
    }

    pub(crate) fn nm_conn_obj_paths_get(&self) -> Result<Vec<String>, NmError> {
        Ok(self
            .setting_proxy
            .list_connections()?
            .into_iter()
            .map(obj_path_to_string)
            .collect())
    }

    pub(crate) fn checkpoint_timeout_extend(
        &self,
        checkpoint: &str,
        added_time_sec: u32,
    ) -> Result<(), NmError> {
        Ok(self.proxy.checkpoint_adjust_rollback_timeout(
            &str_to_obj_path(checkpoint)?,
            added_time_sec,
        )?)
    }

    pub(crate) fn get_dns_configuration(
        &self,
    ) -> Result<Vec<HashMap<String, zvariant::OwnedValue>>, NmError> {
        Ok(self.dns_proxy.configuration()?)
    }

    pub(crate) fn hostname_set(&self, hostname: &str) -> Result<(), NmError> {
        Ok(self.setting_proxy.save_hostname(hostname)?)
    }

    pub(crate) fn global_dns_configuration(
        &self,
    ) -> Result<HashMap<String, zvariant::OwnedValue>, NmError> {
        Ok(self.proxy.global_dns_configuration()?)
    }

    pub(crate) fn set_global_dns_configuration(
        &self,
        value: zvariant::Value,
    ) -> Result<(), NmError> {
        Ok(self.proxy.set_property("GlobalDnsConfiguration", value)?)
    }
}

fn str_to_obj_path(obj_path: &str) -> Result<zvariant::ObjectPath, NmError> {
    zvariant::ObjectPath::try_from(obj_path).map_err(|e| {
        NmError::new(
            ErrorKind::InvalidArgument,
            format!("Invalid object path: {e}"),
        )
    })
}

pub(crate) fn obj_path_to_string(
    obj_path: zvariant::OwnedObjectPath,
) -> String {
    obj_path.into_inner().to_string()
}
