// SPDX-License-Identifier: Apache-2.0

use crate::{
    nm::nm_dbus::NmDevice,
    nm::settings::{
        NM_SETTING_BOND_SETTING_NAME, NM_SETTING_BRIDGE_SETTING_NAME,
        NM_SETTING_DUMMY_SETTING_NAME, NM_SETTING_HSR_SETTING_NAME,
        NM_SETTING_INFINIBAND_SETTING_NAME, NM_SETTING_LOOPBACK_SETTING_NAME,
        NM_SETTING_MACSEC_SETTING_NAME, NM_SETTING_MACVLAN_SETTING_NAME,
        NM_SETTING_OVS_BRIDGE_SETTING_NAME, NM_SETTING_OVS_IFACE_SETTING_NAME,
        NM_SETTING_VETH_SETTING_NAME, NM_SETTING_VLAN_SETTING_NAME,
        NM_SETTING_VRF_SETTING_NAME, NM_SETTING_VXLAN_SETTING_NAME,
        NM_SETTING_WIRED_SETTING_NAME,
    },
    InterfaceType,
};

pub(crate) fn nm_dev_iface_type_to_nmstate(nm_dev: &NmDevice) -> InterfaceType {
    match nm_dev.iface_type.as_str() {
        NM_SETTING_WIRED_SETTING_NAME => InterfaceType::Ethernet,
        NM_SETTING_VETH_SETTING_NAME => InterfaceType::Ethernet,
        NM_SETTING_BOND_SETTING_NAME => InterfaceType::Bond,
        NM_SETTING_DUMMY_SETTING_NAME => InterfaceType::Dummy,
        NM_SETTING_BRIDGE_SETTING_NAME => InterfaceType::LinuxBridge,
        NM_SETTING_OVS_BRIDGE_SETTING_NAME => InterfaceType::OvsBridge,
        NM_SETTING_OVS_IFACE_SETTING_NAME => InterfaceType::OvsInterface,
        NM_SETTING_VRF_SETTING_NAME => InterfaceType::Vrf,
        NM_SETTING_VLAN_SETTING_NAME => InterfaceType::Vlan,
        NM_SETTING_VXLAN_SETTING_NAME => InterfaceType::Vxlan,
        NM_SETTING_MACVLAN_SETTING_NAME => {
            if nm_dev.is_mac_vtap {
                InterfaceType::MacVtap
            } else {
                InterfaceType::MacVlan
            }
        }
        NM_SETTING_LOOPBACK_SETTING_NAME => InterfaceType::Loopback,
        NM_SETTING_INFINIBAND_SETTING_NAME => InterfaceType::InfiniBand,
        NM_SETTING_MACSEC_SETTING_NAME => InterfaceType::MacSec,
        NM_SETTING_HSR_SETTING_NAME => InterfaceType::Hsr,
        _ => InterfaceType::Other(nm_dev.iface_type.to_string()),
    }
}
