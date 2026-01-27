// SPDX-License-Identifier: Apache-2.0

use crate::{
    InterfaceType, NmstateError,
    nm::{
        error::nm_error_to_nmstate,
        nm_dbus::{ErrorKind, NmApi, NmDevice, NmDeviceError, NmIfaceType},
    },
};

fn nm_iface_type_to_nmstate(nm_iface_type: &NmIfaceType) -> InterfaceType {
    match nm_iface_type {
        NmIfaceType::Bridge => InterfaceType::LinuxBridge,
        NmIfaceType::Bond => InterfaceType::Bond,
        NmIfaceType::Ethernet => InterfaceType::Ethernet,
        NmIfaceType::OvsBridge => InterfaceType::OvsBridge,
        NmIfaceType::OvsIface => InterfaceType::OvsInterface,
        NmIfaceType::Vlan => InterfaceType::Vlan,
        NmIfaceType::Vxlan => InterfaceType::Vxlan,
        NmIfaceType::Dummy => InterfaceType::Dummy,
        NmIfaceType::Macvlan => InterfaceType::MacVlan,
        NmIfaceType::Vrf => InterfaceType::Vrf,
        // We unify the Veth to into InterfaceType::Ethernet to simplify
        // work on using veth as plain ethernet interface
        NmIfaceType::Veth => InterfaceType::Ethernet,
        NmIfaceType::Infiniband => InterfaceType::InfiniBand,
        NmIfaceType::Loopback => InterfaceType::Loopback,
        NmIfaceType::Macsec => InterfaceType::MacSec,
        NmIfaceType::Hsr => InterfaceType::Hsr,
        NmIfaceType::IpTunnel => InterfaceType::IpTunnel,
        NmIfaceType::Ipvlan => InterfaceType::IpVlan,
        _ => InterfaceType::Other(nm_iface_type.to_string()),
    }
}

pub(crate) fn nm_dev_iface_type_to_nmstate(nm_dev: &NmDevice) -> InterfaceType {
    let iface_type = nm_iface_type_to_nmstate(&nm_dev.iface_type);

    if iface_type == InterfaceType::MacVlan && nm_dev.is_mac_vtap {
        InterfaceType::MacVtap
    } else {
        iface_type
    }
}

pub(crate) async fn deactivate_nm_devices(
    nm_api: &mut NmApi<'_>,
    nm_devs: &[NmDevice],
) -> Result<(), NmstateError> {
    for nm_dev in nm_devs {
        log::info!("Deactivating device {}", &nm_dev.name);
        if let Err(e) = nm_api.device_disconnect(&nm_dev.obj_path).await
            && e.kind != ErrorKind::Device(NmDeviceError::NotActive)
        {
            return Err(nm_error_to_nmstate(e));
        }
    }
    Ok(())
}
