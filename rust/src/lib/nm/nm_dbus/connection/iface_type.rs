// SPDX-License-Identifier: Apache-2.0

use serde::Deserialize;

use super::super::NmError;

pub(crate) const NM_SETTING_BRIDGE_SETTING_NAME: &str = "bridge";
pub(crate) const NM_SETTING_WIRED_SETTING_NAME: &str = "802-3-ethernet";
pub(crate) const NM_SETTING_OVS_BRIDGE_SETTING_NAME: &str = "ovs-bridge";
pub(crate) const NM_SETTING_OVS_PORT_SETTING_NAME: &str = "ovs-port";
pub(crate) const NM_SETTING_OVS_IFACE_SETTING_NAME: &str = "ovs-interface";
pub(crate) const NM_SETTING_VETH_SETTING_NAME: &str = "veth";
pub(crate) const NM_SETTING_BOND_SETTING_NAME: &str = "bond";
pub(crate) const NM_SETTING_DUMMY_SETTING_NAME: &str = "dummy";
pub(crate) const NM_SETTING_MACSEC_SETTING_NAME: &str = "macsec";
pub(crate) const NM_SETTING_MACVLAN_SETTING_NAME: &str = "macvlan";
pub(crate) const NM_SETTING_VRF_SETTING_NAME: &str = "vrf";
pub(crate) const NM_SETTING_VLAN_SETTING_NAME: &str = "vlan";
pub(crate) const NM_SETTING_VXLAN_SETTING_NAME: &str = "vxlan";
pub(crate) const NM_SETTING_INFINIBAND_SETTING_NAME: &str = "infiniband";
pub(crate) const NM_SETTING_LOOPBACK_SETTING_NAME: &str = "loopback";
pub(crate) const NM_SETTING_HSR_SETTING_NAME: &str = "hsr";
pub(crate) const NM_SETTING_VPN_SETTING_NAME: &str = "vpn";
pub(crate) const NM_SETTING_GENERIC_SETTING_NAME: &str = "generic";
pub(crate) const NM_SETTING_WIRELESS_SETTING_NAME: &str = "802-11-wireless";
pub(crate) const NM_SETTING_BLUETOOTH_SETTING_NAME: &str = "bluetooth";
pub(crate) const NM_SETTING_OLPC_MESH_SETTING_NAME: &str = "802-11-olpc-mesh";
pub(crate) const NM_SETTING_TUN_SETTING_NAME: &str = "tun";
pub(crate) const NM_SETTING_IP_TUNNEL_SETTING_NAME: &str = "ip-tunnel";
pub(crate) const NM_SETTING_PPP_SETTING_NAME: &str = "ppp";
pub(crate) const NM_SETTING_WPAN_SETTING_NAME: &str = "wpan";
pub(crate) const NM_SETTING_6LOWPAN_SETTING_NAME: &str = "6lowpan";
pub(crate) const NM_SETTING_WIREGUARD_SETTING_NAME: &str = "wireguard";
pub(crate) const NM_SETTING_WIFI_P2P_SETTING_NAME: &str = "wifi-p2p";
pub(crate) const NM_SETTING_IPVLAN_SETTING_NAME: &str = "ipvlan";

#[derive(Debug, Clone, PartialEq, Eq, Hash, Default, Deserialize)]
#[non_exhaustive]
pub enum NmIfaceType {
    #[default]
    Unknown,
    Bridge,
    Ethernet,
    OvsBridge,
    OvsPort,
    OvsIface,
    Veth,
    Bond,
    Dummy,
    Macsec,
    Macvlan,
    Vrf,
    Vlan,
    Vxlan,
    Infiniband,
    Loopback,
    Hsr,
    Vpn,
    Generic,
    Wireless,
    Bluetooth,
    OlpcMesh,
    Tun,
    IpTunnel,
    Ppp,
    Wpan,
    SixLowPan,
    Wireguard,
    WifiP2p,
    Ipvlan,
    Other(String),
}

impl std::fmt::Display for NmIfaceType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let iface_str = match self {
            Self::Bridge => NM_SETTING_BRIDGE_SETTING_NAME,
            Self::Ethernet => NM_SETTING_WIRED_SETTING_NAME,
            Self::OvsBridge => NM_SETTING_OVS_BRIDGE_SETTING_NAME,
            Self::OvsPort => NM_SETTING_OVS_PORT_SETTING_NAME,
            Self::OvsIface => NM_SETTING_OVS_IFACE_SETTING_NAME,
            Self::Veth => NM_SETTING_VETH_SETTING_NAME,
            Self::Bond => NM_SETTING_BOND_SETTING_NAME,
            Self::Dummy => NM_SETTING_DUMMY_SETTING_NAME,
            Self::Macsec => NM_SETTING_MACSEC_SETTING_NAME,
            Self::Macvlan => NM_SETTING_MACVLAN_SETTING_NAME,
            Self::Vrf => NM_SETTING_VRF_SETTING_NAME,
            Self::Vlan => NM_SETTING_VLAN_SETTING_NAME,
            Self::Vxlan => NM_SETTING_VXLAN_SETTING_NAME,
            Self::Infiniband => NM_SETTING_INFINIBAND_SETTING_NAME,
            Self::Loopback => NM_SETTING_LOOPBACK_SETTING_NAME,
            Self::Hsr => NM_SETTING_HSR_SETTING_NAME,
            Self::Vpn => NM_SETTING_VPN_SETTING_NAME,
            Self::Generic => NM_SETTING_GENERIC_SETTING_NAME,
            Self::Wireless => NM_SETTING_WIRELESS_SETTING_NAME,
            Self::Bluetooth => NM_SETTING_BLUETOOTH_SETTING_NAME,
            Self::OlpcMesh => NM_SETTING_OLPC_MESH_SETTING_NAME,
            Self::Tun => NM_SETTING_TUN_SETTING_NAME,
            Self::IpTunnel => NM_SETTING_IP_TUNNEL_SETTING_NAME,
            Self::Ppp => NM_SETTING_PPP_SETTING_NAME,
            Self::Wpan => NM_SETTING_WPAN_SETTING_NAME,
            Self::SixLowPan => NM_SETTING_6LOWPAN_SETTING_NAME,
            Self::Wireguard => NM_SETTING_WIREGUARD_SETTING_NAME,
            Self::WifiP2p => NM_SETTING_WIFI_P2P_SETTING_NAME,
            Self::Ipvlan => NM_SETTING_IPVLAN_SETTING_NAME,
            Self::Unknown => "unknown",
            Self::Other(s) => s.as_str(),
        };
        write!(f, "{iface_str}")
    }
}

impl From<&str> for NmIfaceType {
    fn from(s: &str) -> Self {
        match s {
            NM_SETTING_BRIDGE_SETTING_NAME => Self::Bridge,
            NM_SETTING_WIRED_SETTING_NAME => Self::Ethernet,
            NM_SETTING_OVS_BRIDGE_SETTING_NAME => Self::OvsBridge,
            NM_SETTING_OVS_PORT_SETTING_NAME => Self::OvsPort,
            NM_SETTING_OVS_IFACE_SETTING_NAME => Self::OvsIface,
            NM_SETTING_VETH_SETTING_NAME => Self::Veth,
            NM_SETTING_BOND_SETTING_NAME => Self::Bond,
            NM_SETTING_DUMMY_SETTING_NAME => Self::Dummy,
            NM_SETTING_MACSEC_SETTING_NAME => Self::Macsec,
            NM_SETTING_MACVLAN_SETTING_NAME => Self::Macvlan,
            NM_SETTING_VRF_SETTING_NAME => Self::Vrf,
            NM_SETTING_VLAN_SETTING_NAME => Self::Vlan,
            NM_SETTING_VXLAN_SETTING_NAME => Self::Vxlan,
            NM_SETTING_INFINIBAND_SETTING_NAME => Self::Infiniband,
            NM_SETTING_LOOPBACK_SETTING_NAME => Self::Loopback,
            NM_SETTING_HSR_SETTING_NAME => Self::Hsr,
            NM_SETTING_VPN_SETTING_NAME => Self::Vpn,
            NM_SETTING_GENERIC_SETTING_NAME => Self::Generic,
            NM_SETTING_WIRELESS_SETTING_NAME => Self::Wireless,
            NM_SETTING_BLUETOOTH_SETTING_NAME => Self::Bluetooth,
            NM_SETTING_OLPC_MESH_SETTING_NAME => Self::OlpcMesh,
            NM_SETTING_TUN_SETTING_NAME => Self::Tun,
            NM_SETTING_IP_TUNNEL_SETTING_NAME => Self::IpTunnel,
            NM_SETTING_PPP_SETTING_NAME => Self::Ppp,
            NM_SETTING_WPAN_SETTING_NAME => Self::Wpan,
            NM_SETTING_6LOWPAN_SETTING_NAME => Self::SixLowPan,
            NM_SETTING_WIREGUARD_SETTING_NAME => Self::Wireguard,
            NM_SETTING_WIFI_P2P_SETTING_NAME => Self::WifiP2p,
            NM_SETTING_IPVLAN_SETTING_NAME => Self::Ipvlan,
            _ => {
                log::debug!("Unknown interface type {s}");
                Self::Other(s.to_string())
            }
        }
    }
}

impl TryFrom<zvariant::OwnedValue> for NmIfaceType {
    type Error = NmError;

    fn try_from(v: zvariant::OwnedValue) -> Result<NmIfaceType, NmError> {
        Ok(String::try_from(v).map(|v| NmIfaceType::from(v.as_str()))?)
    }
}

#[cfg(feature = "query_apply")]
const CONTROLLER_IFACE_TYPES: [NmIfaceType; 5] = [
    NmIfaceType::Bond,
    NmIfaceType::Bridge,
    NmIfaceType::OvsBridge,
    NmIfaceType::OvsPort,
    NmIfaceType::Vrf,
];

#[cfg(feature = "query_apply")]
impl NmIfaceType {
    pub fn is_controller(&self) -> bool {
        CONTROLLER_IFACE_TYPES.contains(self)
    }
}
