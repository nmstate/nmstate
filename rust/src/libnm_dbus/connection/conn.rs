// Copyright 2021 Red Hat, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

use std::collections::HashMap;
use std::convert::TryFrom;

use log::warn;

use serde::Deserialize;
use zbus::export::zvariant::Signature;
use zvariant::Type;

use crate::{
    connection::bridge::{NmSettingBridge, NmSettingBridgePort},
    connection::ip::NmSettingIp,
    connection::ovs::{
        NmSettingOvsBridge, NmSettingOvsIface, NmSettingOvsPort,
    },
    connection::vlan::NmSettingVlan,
    connection::wired::NmSettingWired,
    dbus::{NM_DBUS_INTERFACE_ROOT, NM_DBUS_INTERFACE_SETTING},
    dbus_value::{own_value_to_bool, own_value_to_i32, own_value_to_string},
    keyfile::zvariant_value_to_keyfile,
    NmError,
};

const NM_AUTOCONENCT_PORT_DEFAULT: i32 = -1;
const NM_AUTOCONENCT_PORT_YES: i32 = 1;
const NM_AUTOCONENCT_PORT_NO: i32 = 0;

pub(crate) type NmConnectionDbusOwnedValue =
    HashMap<String, HashMap<String, zvariant::OwnedValue>>;

pub(crate) type DbusDictionary = HashMap<String, zvariant::OwnedValue>;

pub(crate) type NmConnectionDbusValue<'a> =
    HashMap<&'a str, HashMap<&'a str, zvariant::Value<'a>>>;

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "NmConnectionDbusOwnedValue")]
pub struct NmConnection {
    pub connection: Option<NmSettingConnection>,
    pub bridge: Option<NmSettingBridge>,
    pub bridge_port: Option<NmSettingBridgePort>,
    pub ipv4: Option<NmSettingIp>,
    pub ipv6: Option<NmSettingIp>,
    pub ovs_bridge: Option<NmSettingOvsBridge>,
    pub ovs_port: Option<NmSettingOvsPort>,
    pub ovs_iface: Option<NmSettingOvsIface>,
    pub wired: Option<NmSettingWired>,
    pub vlan: Option<NmSettingVlan>,
    #[serde(skip)]
    pub(crate) obj_path: String,
    _other: HashMap<String, HashMap<String, zvariant::OwnedValue>>,
}

// The signature is the same as the NmConnectionDbusOwnedValue because we are going through the
// try_from
impl Type for NmConnection {
    fn signature() -> Signature<'static> {
        NmConnectionDbusOwnedValue::signature()
    }
}

impl TryFrom<NmConnectionDbusOwnedValue> for NmConnection {
    type Error = NmError;
    fn try_from(
        mut value: NmConnectionDbusOwnedValue,
    ) -> Result<Self, Self::Error> {
        Ok(Self {
            connection: value
                .remove("connection")
                .map(NmSettingConnection::try_from)
                .transpose()?,
            ipv4: value
                .remove("ipv4")
                .map(NmSettingIp::try_from)
                .transpose()?,
            ipv6: value
                .remove("ipv6")
                .map(NmSettingIp::try_from)
                .transpose()?,
            bridge: value
                .remove("bridge")
                .map(NmSettingBridge::try_from)
                .transpose()?,
            bridge_port: value
                .remove("bridge-port")
                .map(NmSettingBridgePort::try_from)
                .transpose()?,
            ovs_bridge: value
                .remove("ovs-bridge")
                .map(NmSettingOvsBridge::try_from)
                .transpose()?,
            ovs_port: value
                .remove("ovs-port")
                .map(NmSettingOvsPort::try_from)
                .transpose()?,
            ovs_iface: value
                .remove("ovs-interface")
                .map(NmSettingOvsIface::try_from)
                .transpose()?,
            wired: value
                .remove("802-3-ethernet")
                .map(NmSettingWired::try_from)
                .transpose()?,
            vlan: value
                .remove("vlan")
                .map(NmSettingVlan::try_from)
                .transpose()?,
            _other: value,
            ..Default::default()
        })
    }
}

impl NmConnection {
    pub fn new() -> Self {
        Default::default()
    }

    pub fn iface_name(&self) -> Option<&str> {
        if let Some(NmSettingConnection {
            iface_name: Some(iface_name),
            ..
        }) = &self.connection
        {
            Some(iface_name.as_str())
        } else {
            None
        }
    }

    pub fn iface_type(&self) -> Option<&str> {
        if let Some(NmSettingConnection {
            iface_type: Some(iface_type),
            ..
        }) = &self.connection
        {
            Some(iface_type.as_str())
        } else {
            None
        }
    }

    pub fn controller(&self) -> Option<&str> {
        if let Some(NmSettingConnection {
            controller: Some(ctrl),
            ..
        }) = &self.connection
        {
            Some(ctrl.as_str())
        } else {
            None
        }
    }

    pub fn controller_type(&self) -> Option<&str> {
        if let Some(NmSettingConnection {
            controller_type: Some(ctrl),
            ..
        }) = &self.connection
        {
            Some(ctrl.as_str())
        } else {
            None
        }
    }

    pub fn to_keyfile(&self) -> Result<String, NmError> {
        let mut nm_conn_dbus_value = self.to_value()?;

        // section name `802-3-ethernet` should renamed to `ethernet`
        if let Some(wire_setting) = nm_conn_dbus_value.remove("802-3-ethernet")
        {
            nm_conn_dbus_value.insert("ethernet", wire_setting);
        }

        let nm_conn_value = zvariant::Dict::from(nm_conn_dbus_value);

        zvariant_value_to_keyfile(&zvariant::Value::Dict(nm_conn_value), "")
    }

    pub(crate) fn to_value(&self) -> Result<NmConnectionDbusValue, NmError> {
        let mut ret = HashMap::new();
        if let Some(con_set) = &self.connection {
            ret.insert("connection", con_set.to_value()?);
        }
        if let Some(br_set) = &self.bridge {
            ret.insert("bridge", br_set.to_value()?);
        }
        if let Some(br_port_set) = &self.bridge_port {
            ret.insert("bridge-port", br_port_set.to_value()?);
        }
        if let Some(ipv4_set) = &self.ipv4 {
            ret.insert("ipv4", ipv4_set.to_value()?);
        }
        if let Some(ipv6_set) = &self.ipv6 {
            ret.insert("ipv6", ipv6_set.to_value()?);
        }
        if let Some(ovs_bridge_set) = &self.ovs_bridge {
            ret.insert("ovs-bridge", ovs_bridge_set.to_value()?);
        }
        if let Some(ovs_port_set) = &self.ovs_port {
            ret.insert("ovs-port", ovs_port_set.to_value()?);
        }
        if let Some(ovs_iface_set) = &self.ovs_iface {
            ret.insert("ovs-interface", ovs_iface_set.to_value()?);
        }
        if let Some(wired_set) = &self.wired {
            ret.insert("802-3-ethernet", wired_set.to_value()?);
        }
        if let Some(vlan) = &self.vlan {
            ret.insert("vlan", vlan.to_value()?);
        }
        for (key, setting_value) in &self._other {
            let mut other_setting_value: HashMap<&str, zvariant::Value> =
                HashMap::new();
            for (sub_key, sub_value) in setting_value {
                other_setting_value.insert(
                    sub_key.as_str(),
                    zvariant::Value::from(sub_value.clone()),
                );
            }
            ret.insert(key, other_setting_value);
        }
        Ok(ret)
    }

    pub fn uuid(&self) -> Option<&str> {
        if let Some(nm_conn_set) = &self.connection {
            if let Some(ref uuid) = nm_conn_set.uuid {
                return Some(uuid);
            }
        }
        None
    }
}

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
pub struct NmSettingConnection {
    pub id: Option<String>,
    pub uuid: Option<String>,
    pub iface_type: Option<String>,
    pub iface_name: Option<String>,
    pub controller: Option<String>,
    pub controller_type: Option<String>,
    pub autoconnect: Option<bool>,
    pub autoconnect_ports: Option<bool>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingConnection {
    type Error = NmError;
    fn try_from(
        mut setting_value: DbusDictionary,
    ) -> Result<Self, Self::Error> {
        let mut setting = Self::new();
        setting.id = setting_value
            .remove("id")
            .map(own_value_to_string)
            .transpose()?;
        setting.uuid = setting_value
            .remove("uuid")
            .map(own_value_to_string)
            .transpose()?;
        setting.iface_type = setting_value
            .remove("type")
            .map(own_value_to_string)
            .transpose()?;
        setting.iface_name = setting_value
            .remove("interface-name")
            .map(own_value_to_string)
            .transpose()?;
        setting.controller = setting_value
            .remove("master")
            .map(own_value_to_string)
            .transpose()?;
        setting.controller_type = setting_value
            .remove("slave-type")
            .map(own_value_to_string)
            .transpose()?;
        setting.autoconnect = setting_value
            .remove("autoconnect")
            .map(own_value_to_bool)
            .transpose()?;
        setting.autoconnect_ports = match setting_value
            .remove("autoconnect-slaves")
            .map(own_value_to_i32)
            .transpose()?
        {
            Some(NM_AUTOCONENCT_PORT_YES) => Some(true),
            Some(NM_AUTOCONENCT_PORT_NO) => Some(false),
            Some(v) => {
                warn!("Unknown autoconnect-ports value {}", v);
                None
            }
            // For autoconnect, None means true
            None => Some(true),
        };
        setting._other = setting_value;

        if setting.autoconnect == None {
            // For autoconnect, None means true
            setting.autoconnect = Some(true)
        }

        Ok(setting)
    }
}

impl NmSettingConnection {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.id {
            ret.insert("id", zvariant::Value::new(v.as_str()));
        }
        if let Some(v) = &self.uuid {
            ret.insert("uuid", zvariant::Value::new(v.as_str()));
        }
        if let Some(v) = &self.iface_type {
            ret.insert("type", zvariant::Value::new(v.as_str()));
        }
        if let Some(v) = &self.iface_name {
            ret.insert("interface-name", zvariant::Value::new(v.as_str()));
        }
        if let Some(v) = &self.controller {
            ret.insert("master", zvariant::Value::new(v.as_str()));
        }
        if let Some(v) = &self.controller_type {
            ret.insert("slave-type", zvariant::Value::new(v.as_str()));
        }

        ret.insert(
            "autoconnect",
            if let Some(false) = &self.autoconnect {
                zvariant::Value::new(false)
            } else {
                zvariant::Value::new(true)
            },
        );
        ret.insert(
            "autoconnect-slaves",
            match &self.autoconnect_ports {
                Some(true) => zvariant::Value::new(NM_AUTOCONENCT_PORT_YES),
                Some(false) => zvariant::Value::new(NM_AUTOCONENCT_PORT_NO),
                None => zvariant::Value::new(NM_AUTOCONENCT_PORT_DEFAULT),
            },
        );
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

pub(crate) fn nm_con_get_from_obj_path(
    dbus_con: &zbus::Connection,
    con_obj_path: &str,
) -> Result<NmConnection, NmError> {
    let proxy = zbus::Proxy::new(
        dbus_con,
        NM_DBUS_INTERFACE_ROOT,
        con_obj_path,
        NM_DBUS_INTERFACE_SETTING,
    )?;
    let mut nm_conn = proxy.call::<(), NmConnection>("GetSettings", &())?;
    nm_conn.obj_path = con_obj_path.to_string();
    Ok(nm_conn)
}
