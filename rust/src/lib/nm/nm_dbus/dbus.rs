// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use log::debug;
use zbus::proxy;

use super::{
    connection::{NmConnection, NmConnectionDbusValue},
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

// These proxy() macros only generate private struct, hence it should be
// sit with its consumer.
#[proxy(
    interface = "org.freedesktop.NetworkManager",
    default_service = "org.freedesktop.NetworkManager",
    default_path = "/org/freedesktop/NetworkManager"
)]
trait NetworkManager {
    #[zbus(property)]
    fn version(&self) -> zbus::Result<String>;

    #[zbus(property)]
    fn version_info(&self) -> zbus::Result<Vec<u32>>;

    #[zbus(property)]
    fn active_connections(
        &self,
    ) -> zbus::Result<Vec<zvariant::OwnedObjectPath>>;

    #[zbus(property)]
    fn checkpoints(&self) -> zbus::Result<Vec<zvariant::OwnedObjectPath>>;

    #[zbus(property)]
    fn global_dns_configuration(
        &self,
    ) -> zbus::Result<HashMap<String, zvariant::OwnedValue>>;

    #[zbus(property)]
    fn set_global_dns_configuration(
        &self,
        value: zvariant::Value<'_>,
    ) -> zbus::Result<()>;

    /// CheckpointCreate method
    fn checkpoint_create(
        &self,
        devices: &[zvariant::ObjectPath<'_>],
        rollback_timeout: u32,
        flags: u32,
    ) -> zbus::Result<zvariant::OwnedObjectPath>;

    /// CheckpointDestroy method
    fn checkpoint_destroy(
        &self,
        checkpoint: &zvariant::ObjectPath<'_>,
    ) -> zbus::Result<()>;

    /// CheckpointRollback method
    fn checkpoint_rollback(
        &self,
        checkpoint: &zvariant::ObjectPath<'_>,
    ) -> zbus::Result<HashMap<String, u32>>;

    /// ActivateConnection method
    fn activate_connection(
        &self,
        connection: &zvariant::ObjectPath<'_>,
        device: &zvariant::ObjectPath<'_>,
        specific_object: &zvariant::ObjectPath<'_>,
    ) -> zbus::Result<zvariant::OwnedObjectPath>;

    /// DeactivateConnection method
    fn deactivate_connection(
        &self,
        active_connection: &zvariant::ObjectPath<'_>,
    ) -> zbus::Result<()>;

    /// GetAllDevices method
    fn get_all_devices(&self) -> zbus::Result<Vec<zvariant::OwnedObjectPath>>;

    /// CheckpointAdjustRollbackTimeout method
    fn checkpoint_adjust_rollback_timeout(
        &self,
        checkpoint: &zvariant::ObjectPath<'_>,
        add_timeout: u32,
    ) -> zbus::Result<()>;
}

#[proxy(
    interface = "org.freedesktop.NetworkManager.Settings",
    default_service = "org.freedesktop.NetworkManager",
    default_path = "/org/freedesktop/NetworkManager/Settings"
)]
trait NetworkManagerSetting {
    /// GetConnectionByUuid method
    fn get_connection_by_uuid(
        &self,
        uuid: &str,
    ) -> zbus::Result<zvariant::OwnedObjectPath>;

    /// AddConnection2 method
    fn add_connection2(
        &self,
        settings: HashMap<&str, HashMap<&str, zvariant::Value<'_>>>,
        flags: u32,
        args: HashMap<&str, zvariant::Value<'_>>,
    ) -> zbus::Result<(
        zvariant::OwnedObjectPath,
        HashMap<String, zvariant::OwnedValue>,
    )>;

    /// ListConnections method
    fn list_connections(&self) -> zbus::Result<Vec<zvariant::OwnedObjectPath>>;

    /// GetAllDevices method
    fn get_all_devices(&self) -> zbus::Result<Vec<zvariant::OwnedObjectPath>>;

    /// SaveHostname method
    fn save_hostname(&self, hostname: &str) -> zbus::Result<()>;
}

#[proxy(
    interface = "org.freedesktop.NetworkManager.DnsManager",
    default_service = "org.freedesktop.NetworkManager",
    default_path = "/org/freedesktop/NetworkManager/DnsManager"
)]
trait NetworkManagerDns {
    /// Configuration property
    #[zbus(property)]
    fn configuration(
        &self,
    ) -> zbus::Result<Vec<HashMap<String, zvariant::OwnedValue>>>;
}

pub(crate) struct NmDbus<'a> {
    pub(crate) connection: zbus::Connection,
    proxy: NetworkManagerProxy<'a>,
    setting_proxy: NetworkManagerSettingProxy<'a>,
    dns_proxy: NetworkManagerDnsProxy<'a>,
}

impl NmDbus<'_> {
    pub(crate) async fn new() -> Result<Self, NmError> {
        let connection = zbus::Connection::system().await?;
        let proxy = NetworkManagerProxy::new(&connection).await?;
        let setting_proxy =
            NetworkManagerSettingProxy::new(&connection).await?;
        let dns_proxy = NetworkManagerDnsProxy::new(&connection).await?;

        Ok(Self {
            connection,
            proxy,
            setting_proxy,
            dns_proxy,
        })
    }

    pub(crate) async fn version(&self) -> Result<String, NmError> {
        Ok(self.proxy.version().await?)
    }

    pub(crate) async fn version_info(&self) -> Result<Vec<u32>, NmError> {
        Ok(self.proxy.version_info().await?)
    }

    async fn _checkpoint_create(
        &self,
        timeout: u32,
        flags: u32,
    ) -> Result<String, NmError> {
        match self.proxy.checkpoint_create(&[], timeout, flags).await {
            Ok(cp) => Ok(obj_path_to_string(cp)),
            Err(e) => {
                Err(if let zbus::Error::MethodError(ref error_type, ..) = e {
                    if error_type.as_str()
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

    pub(crate) async fn checkpoint_create(
        &self,
        timeout: u32,
    ) -> Result<String, NmError> {
        let default_flags = NM_CHECKPOINT_CREATE_FLAG_DELETE_NEW_CONNECTIONS
            | NM_CHECKPOINT_CREATE_FLAG_DISCONNECT_NEW_DEVICES;
        match self
            ._checkpoint_create(
                timeout,
                default_flags
                    | NM_CHECKPOINT_CREATE_FLAG_TRACK_INTERNAL_GLOBAL_DNS,
            )
            .await
        {
            Ok(s) => Ok(s),
            Err(_) => {
                // The NM_CHECKPOINT_CREATE_FLAG_TRACK_INTERNAL_GLOBAL_DNS is
                // supported by NM 1.47+ and might be backported to other
                // versions. There is no way to know whether it is supported or
                // not by checking the NM version. Hence we try to create
                // the checkpoint without this flag on second try.
                self._checkpoint_create(timeout, default_flags).await
            }
        }
    }

    pub(crate) async fn checkpoint_destroy(
        &self,
        checkpoint: &str,
    ) -> Result<(), NmError> {
        debug!("checkpoint_destroy: {}", checkpoint);
        Ok(self
            .proxy
            .checkpoint_destroy(&str_to_obj_path(checkpoint)?)
            .await?)
    }

    pub(crate) async fn checkpoint_rollback(
        &self,
        checkpoint: &str,
    ) -> Result<(), NmError> {
        debug!("checkpoint_rollback: {}", checkpoint);
        self.proxy
            .checkpoint_rollback(&str_to_obj_path(checkpoint)?)
            .await?;
        Ok(())
    }

    pub(crate) async fn checkpoints(&self) -> Result<Vec<String>, NmError> {
        Ok(self
            .proxy
            .checkpoints()
            .await?
            .into_iter()
            .map(obj_path_to_string)
            .collect())
    }

    pub(crate) async fn get_conn_obj_path_by_uuid(
        &self,
        uuid: &str,
    ) -> Result<String, NmError> {
        match self.setting_proxy.get_connection_by_uuid(uuid).await {
            Ok(c) => Ok(obj_path_to_string(c)),
            Err(e) => {
                if let zbus::Error::MethodError(ref error_type, ..) = e {
                    if error_type.as_str()
                        == format!(
                            "{NM_DBUS_INTERFACE_ROOT}.\
                            Settings.InvalidConnection",
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

    pub(crate) async fn connection_activate(
        &self,
        nm_conn: &str,
    ) -> Result<(), NmError> {
        self.proxy
            .activate_connection(
                &str_to_obj_path(nm_conn)?,
                &str_to_obj_path(OBJ_PATH_NULL_STR)?,
                &str_to_obj_path(OBJ_PATH_NULL_STR)?,
            )
            .await?;
        Ok(())
    }

    pub(crate) async fn active_connections(
        &self,
    ) -> Result<Vec<String>, NmError> {
        Ok(self
            .proxy
            .active_connections()
            .await?
            .into_iter()
            .map(obj_path_to_string)
            .collect())
    }

    pub(crate) async fn connection_deactivate(
        &self,
        nm_ac: &str,
    ) -> Result<(), NmError> {
        Ok(self
            .proxy
            .deactivate_connection(&str_to_obj_path(nm_ac)?)
            .await?)
    }

    pub(crate) async fn connection_add(
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
            .add_connection2(value, flags, HashMap::new())
            .await?;
        Ok(())
    }

    pub(crate) async fn connection_delete(
        &self,
        con_obj_path: &str,
    ) -> Result<(), NmError> {
        debug!("connection_delete: {}", con_obj_path);
        let proxy = zbus::Proxy::new(
            &self.connection,
            NM_DBUS_INTERFACE_ROOT,
            con_obj_path,
            NM_DBUS_INTERFACE_SETTING,
        )
        .await?;
        Ok(proxy.call::<&str, (), ()>("Delete", &()).await?)
    }

    pub(crate) async fn connection_update(
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
        )
        .await?;
        let flags = NM_SETTINGS_UPDATE2_FLAGS_BLOCK_AUTOCONNECT
            + if memory_only {
                NM_SETTINGS_UPDATE2_FLAGS_IN_MEMORY
            } else {
                NM_SETTINGS_UPDATE2_FLAGS_TO_DISK
            };
        proxy.call::<&str, (
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
            ).await?;
        Ok(())
    }

    pub(crate) async fn nm_dev_obj_paths_get(
        &self,
    ) -> Result<Vec<String>, NmError> {
        Ok(self
            .proxy
            .get_all_devices()
            .await?
            .into_iter()
            .map(obj_path_to_string)
            .collect())
    }

    pub(crate) async fn nm_dev_applied_connection_get(
        &self,
        nm_dev_obj_path: &str,
    ) -> Result<NmConnection, NmError> {
        let proxy = zbus::Proxy::new(
            &self.connection,
            NM_DBUS_INTERFACE_ROOT,
            nm_dev_obj_path,
            NM_DBUS_INTERFACE_DEVICE,
        )
        .await?;
        let (nm_conn, _) = proxy
            .call::<&str, u32, (NmConnection, u64)>(
                "GetAppliedConnection",
                &(
                    0
                    // NM document require it to be zero
                ),
            )
            .await?;
        Ok(nm_conn)
    }

    pub(crate) async fn nm_dev_reapply(
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
        )
        .await?;
        match proxy
            .call::<&str, (NmConnectionDbusValue, u64, u32), ()>(
                "Reapply",
                &(
                    value, 0, /* ignore version id */
                    0, /* flag, NM document require always be zero */
                ),
            )
            .await
        {
            Ok(()) => Ok(()),
            Err(e) => {
                if let zbus::Error::MethodError(
                    ref error_type,
                    Some(ref err_msg),
                    ..,
                ) = e
                {
                    if error_type.as_str()
                        == format!(
                            "{NM_DBUS_INTERFACE_ROOT}.\
                            Device.IncompatibleConnection"
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

    pub(crate) async fn nm_conn_obj_paths_get(
        &self,
    ) -> Result<Vec<String>, NmError> {
        Ok(self
            .setting_proxy
            .list_connections()
            .await?
            .into_iter()
            .map(obj_path_to_string)
            .collect())
    }

    pub(crate) async fn checkpoint_timeout_extend(
        &self,
        checkpoint: &str,
        added_time_sec: u32,
    ) -> Result<(), NmError> {
        Ok(self
            .proxy
            .checkpoint_adjust_rollback_timeout(
                &str_to_obj_path(checkpoint)?,
                added_time_sec,
            )
            .await?)
    }

    pub(crate) async fn get_dns_configuration(
        &self,
    ) -> Result<Vec<HashMap<String, zvariant::OwnedValue>>, NmError> {
        Ok(self.dns_proxy.configuration().await?)
    }

    pub(crate) async fn hostname_set(
        &self,
        hostname: &str,
    ) -> Result<(), NmError> {
        Ok(self.setting_proxy.save_hostname(hostname).await?)
    }

    pub(crate) async fn global_dns_configuration(
        &self,
    ) -> Result<HashMap<String, zvariant::OwnedValue>, NmError> {
        Ok(self.proxy.global_dns_configuration().await?)
    }

    pub(crate) async fn set_global_dns_configuration(
        &self,
        value: zvariant::Value<'_>,
    ) -> Result<(), NmError> {
        Ok(self.proxy.set_global_dns_configuration(value).await?)
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
