// SPDX-License-Identifier: Apache-2.0

use std::convert::TryFrom;

use super::super::{
    connection::DbusDictionary,
    dbus::{NM_DBUS_INTERFACE_DEV, NM_DBUS_INTERFACE_ROOT},
    lldp::NmLldpNeighbor,
    ErrorKind, NmDevice, NmDeviceState, NmDeviceStateReason, NmError,
};

const NM_DEVICE_TYPE_UNKNOWN: u32 = 0;
const NM_DEVICE_TYPE_ETHERNET: u32 = 1;
const NM_DEVICE_TYPE_WIFI: u32 = 2;
// const NM_DEVICE_TYPE_UNUSED1: u32 = 3;
// const NM_DEVICE_TYPE_UNUSED2: u32 = 4;
const NM_DEVICE_TYPE_BT: u32 = 5;
const NM_DEVICE_TYPE_OLPC_MESH: u32 = 6;
const NM_DEVICE_TYPE_WIMAX: u32 = 7;
const NM_DEVICE_TYPE_MODEM: u32 = 8;
const NM_DEVICE_TYPE_INFINIBAND: u32 = 9;
const NM_DEVICE_TYPE_BOND: u32 = 10;
const NM_DEVICE_TYPE_VLAN: u32 = 11;
const NM_DEVICE_TYPE_ADSL: u32 = 12;
const NM_DEVICE_TYPE_BRIDGE: u32 = 13;
const NM_DEVICE_TYPE_GENERIC: u32 = 14;
const NM_DEVICE_TYPE_TEAM: u32 = 15;
const NM_DEVICE_TYPE_TUN: u32 = 16;
const NM_DEVICE_TYPE_IP_TUNNEL: u32 = 17;
const NM_DEVICE_TYPE_MACVLAN: u32 = 18;
const NM_DEVICE_TYPE_VXLAN: u32 = 19;
const NM_DEVICE_TYPE_VETH: u32 = 20;
const NM_DEVICE_TYPE_MACSEC: u32 = 21;
const NM_DEVICE_TYPE_DUMMY: u32 = 22;
const NM_DEVICE_TYPE_PPP: u32 = 23;
const NM_DEVICE_TYPE_OVS_INTERFACE: u32 = 24;
const NM_DEVICE_TYPE_OVS_PORT: u32 = 25;
const NM_DEVICE_TYPE_OVS_BRIDGE: u32 = 26;
const NM_DEVICE_TYPE_WPAN: u32 = 27;
const NM_DEVICE_TYPE_6LOWPAN: u32 = 28;
const NM_DEVICE_TYPE_WIREGUARD: u32 = 29;
const NM_DEVICE_TYPE_WIFI_P2P: u32 = 30;
const NM_DEVICE_TYPE_VRF: u32 = 31;
const NM_DEVICE_TYPE_LOOPBACK: u32 = 32;

fn nm_dev_name_get(
    dbus_conn: &zbus::Connection,
    obj_path: &str,
) -> Result<String, NmError> {
    let proxy = zbus::Proxy::new(
        dbus_conn,
        NM_DBUS_INTERFACE_ROOT,
        obj_path,
        NM_DBUS_INTERFACE_DEV,
    )?;
    match proxy.get_property::<String>("Interface") {
        Ok(n) => Ok(n),
        Err(e) => Err(NmError::new(
            ErrorKind::Bug,
            format!(
                "Failed to retrieve interface name of device {obj_path}: {e}"
            ),
        )),
    }
}

fn nm_dev_iface_type_get(
    dbus_conn: &zbus::Connection,
    obj_path: &str,
) -> Result<String, NmError> {
    let proxy = zbus::Proxy::new(
        dbus_conn,
        NM_DBUS_INTERFACE_ROOT,
        obj_path,
        NM_DBUS_INTERFACE_DEV,
    )?;
    match proxy.get_property::<u32>("DeviceType") {
        Ok(i) => Ok(match i {
            // Using the NM_SETTING_*_NAME string
            NM_DEVICE_TYPE_UNKNOWN => "unknown".to_string(),
            NM_DEVICE_TYPE_ETHERNET => "802-3-ethernet".to_string(),
            NM_DEVICE_TYPE_WIFI => "802-11-wireless".to_string(),
            NM_DEVICE_TYPE_BT => "bluetooth".to_string(),
            NM_DEVICE_TYPE_OLPC_MESH => "802-11-olpc-mesh".to_string(),
            NM_DEVICE_TYPE_WIMAX => "wimax".to_string(),
            NM_DEVICE_TYPE_MODEM => "modem".to_string(),
            NM_DEVICE_TYPE_INFINIBAND => "infiniband".to_string(),
            NM_DEVICE_TYPE_BOND => "bond".to_string(),
            NM_DEVICE_TYPE_VLAN => "vlan".to_string(),
            NM_DEVICE_TYPE_ADSL => "adsl".to_string(),
            NM_DEVICE_TYPE_BRIDGE => "bridge".to_string(),
            NM_DEVICE_TYPE_GENERIC => "generic".to_string(),
            NM_DEVICE_TYPE_TEAM => "team".to_string(),
            NM_DEVICE_TYPE_TUN => "tun".to_string(),
            NM_DEVICE_TYPE_IP_TUNNEL => "ip-tunnel".to_string(),
            NM_DEVICE_TYPE_MACVLAN => "macvlan".to_string(),
            NM_DEVICE_TYPE_VXLAN => "vxlan".to_string(),
            NM_DEVICE_TYPE_VETH => "veth".to_string(),
            NM_DEVICE_TYPE_MACSEC => "macsec".to_string(),
            NM_DEVICE_TYPE_DUMMY => "dummy".to_string(),
            NM_DEVICE_TYPE_PPP => "ppp".to_string(),
            NM_DEVICE_TYPE_OVS_INTERFACE => "ovs-interface".to_string(),
            NM_DEVICE_TYPE_OVS_PORT => "ovs-port".to_string(),
            NM_DEVICE_TYPE_OVS_BRIDGE => "ovs-bridge".to_string(),
            NM_DEVICE_TYPE_WPAN => "wpan".to_string(),
            NM_DEVICE_TYPE_6LOWPAN => "6lowpan".to_string(),
            NM_DEVICE_TYPE_WIREGUARD => "wireguard".to_string(),
            NM_DEVICE_TYPE_WIFI_P2P => "wifi-p2p".to_string(),
            NM_DEVICE_TYPE_VRF => "vrf".to_string(),
            NM_DEVICE_TYPE_LOOPBACK => "loopback".to_string(),
            _ => format!("unknown({i})"),
        }),
        Err(e) => Err(NmError::new(
            ErrorKind::Bug,
            format!("Failed to retrieve device type of device {obj_path}: {e}"),
        )),
    }
}

fn nm_dev_state_reason_get(
    dbus_conn: &zbus::Connection,
    obj_path: &str,
) -> Result<(NmDeviceState, NmDeviceStateReason), NmError> {
    let proxy = zbus::Proxy::new(
        dbus_conn,
        NM_DBUS_INTERFACE_ROOT,
        obj_path,
        NM_DBUS_INTERFACE_DEV,
    )?;
    match proxy.get_property::<(u32, u32)>("StateReason") {
        Ok((state, state_reason)) => Ok((state.into(), state_reason.into())),
        Err(e) => Err(NmError::new(
            ErrorKind::Bug,
            format!(
                "Failed to retrieve state reason of device {obj_path}: {e}"
            ),
        )),
    }
}

fn nm_dev_is_mac_vtap_get(
    dbus_conn: &zbus::Connection,
    obj_path: &str,
) -> Result<bool, NmError> {
    let dbus_iface = format!("{NM_DBUS_INTERFACE_DEV}.Macvlan");
    let proxy = zbus::Proxy::new(
        dbus_conn,
        NM_DBUS_INTERFACE_ROOT,
        obj_path,
        &dbus_iface,
    )?;
    match proxy.get_property::<bool>("Tab") {
        Ok(v) => Ok(v),
        Err(e) => Err(NmError::new(
            ErrorKind::Bug,
            format!(
                "Failed to retrieve Macvlan.Tab(tap) of device {obj_path}: {e}"
            ),
        )),
    }
}

fn nm_dev_real_get(
    dbus_conn: &zbus::Connection,
    obj_path: &str,
) -> Result<bool, NmError> {
    let proxy = zbus::Proxy::new(
        dbus_conn,
        NM_DBUS_INTERFACE_ROOT,
        obj_path,
        NM_DBUS_INTERFACE_DEV,
    )?;
    match proxy.get_property::<bool>("Real") {
        Ok(r) => Ok(r),
        Err(e) => Err(NmError::new(
            ErrorKind::Bug,
            format!("Failed to retrieve real of device {obj_path}: {e}"),
        )),
    }
}

pub(crate) fn nm_dev_from_obj_path(
    dbus_conn: &zbus::Connection,
    obj_path: &str,
) -> Result<NmDevice, NmError> {
    let real = nm_dev_real_get(dbus_conn, obj_path)?;
    let (state, state_reason) = nm_dev_state_reason_get(dbus_conn, obj_path)?;
    let mut dev = NmDevice {
        name: nm_dev_name_get(dbus_conn, obj_path)?,
        iface_type: nm_dev_iface_type_get(dbus_conn, obj_path)?,
        state,
        state_reason,
        obj_path: obj_path.to_string(),
        is_mac_vtap: false,
        real,
    };
    if dev.iface_type == "macvlan" {
        dev.is_mac_vtap = nm_dev_is_mac_vtap_get(dbus_conn, obj_path)?;
    }
    Ok(dev)
}

pub(crate) fn nm_dev_delete(
    dbus_conn: &zbus::Connection,
    obj_path: &str,
) -> Result<(), NmError> {
    let proxy = zbus::Proxy::new(
        dbus_conn,
        NM_DBUS_INTERFACE_ROOT,
        obj_path,
        NM_DBUS_INTERFACE_DEV,
    )?;
    match proxy.call::<(), ()>("Delete", &()) {
        Ok(()) => Ok(()),
        Err(e) => Err(NmError::new(
            ErrorKind::Bug,
            format!("Failed to delete device {obj_path}: {e}"),
        )),
    }
}

pub(crate) fn nm_dev_get_llpd(
    dbus_conn: &zbus::Connection,
    obj_path: &str,
) -> Result<Vec<NmLldpNeighbor>, NmError> {
    let proxy = zbus::Proxy::new(
        dbus_conn,
        NM_DBUS_INTERFACE_ROOT,
        obj_path,
        NM_DBUS_INTERFACE_DEV,
    )?;
    match proxy.get_property::<Vec<DbusDictionary>>("LldpNeighbors") {
        Ok(v) => {
            let mut ret = Vec::new();
            for value in v {
                ret.push(NmLldpNeighbor::try_from(value)?);
            }
            Ok(ret)
        }
        Err(e) => Err(NmError::new(
            ErrorKind::Bug,
            format!(
                "Failed to retrieve LLDP neighbors of device {obj_path}: {e}"
            ),
        )),
    }
}
