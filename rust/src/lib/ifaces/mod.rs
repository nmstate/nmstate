// SPDX-License-Identifier: Apache-2.0

mod alt_name;
mod base;
mod bond;
mod bridge_vlan;
mod dummy;
mod ethernet;
mod ethtool;
mod hsr;
pub(crate) mod inter_ifaces;
mod ip_tunnel;
mod ipsec;
mod ipvlan;
mod loopback;
mod vrf;
mod vxlan;
mod xfrm;
// The pub(crate) is only for unit test
mod infiniband;
pub(crate) mod inter_ifaces_controller;
mod linux_bridge;
mod mac_vlan;
mod mac_vtap;
mod macsec;
mod ovs;
mod sriov;
mod vlan;

pub use base::*;
pub use bond::{
    BondAdSelect, BondAllPortsActive, BondArpAllTargets, BondArpValidate,
    BondConfig, BondFailOverMac, BondInterface, BondLacpRate, BondMode,
    BondOptions, BondPortConfig, BondPrimaryReselect, BondXmitHashPolicy,
};
pub use bridge_vlan::{
    BridgePortTrunkTag, BridgePortVlanConfig, BridgePortVlanMode,
    BridgePortVlanRange,
};
pub use dummy::DummyInterface;
pub use ethernet::{
    EthernetConfig, EthernetDuplex, EthernetInterface, VethConfig,
};
pub use ethtool::{
    EthtoolCoalesceConfig, EthtoolConfig, EthtoolFeatureConfig,
    EthtoolFecConfig, EthtoolFecMode, EthtoolPauseConfig, EthtoolRingConfig,
};
pub use hsr::{HsrConfig, HsrInterface, HsrProtocol};
pub use infiniband::{InfiniBandConfig, InfiniBandInterface, InfiniBandMode};
pub use inter_ifaces::*;
pub use ip_tunnel::{
    Ip6TunnelFlag, IpTunnelConfig, IpTunnelInterface, IpTunnelMode,
};
pub use ipsec::{
    IpsecInterface, LibreswanAddressFamily, LibreswanConfig,
    LibreswanConnectionType,
};
pub use ipvlan::{IpVlanConfig, IpVlanInterface, IpVlanMode};
pub use linux_bridge::{
    LinuxBridgeConfig, LinuxBridgeInterface, LinuxBridgeMulticastRouterType,
    LinuxBridgeOptions, LinuxBridgePortConfig, LinuxBridgeStpOptions,
};
pub use loopback::LoopbackInterface;
pub use mac_vlan::{MacVlanConfig, MacVlanInterface, MacVlanMode};
pub use mac_vtap::{MacVtapConfig, MacVtapInterface, MacVtapMode};
pub use macsec::{
    MacSecConfig, MacSecInterface, MacSecOffload, MacSecValidate,
};
pub use ovs::{
    OvsBridgeBondConfig, OvsBridgeBondMode, OvsBridgeBondPortConfig,
    OvsBridgeConfig, OvsBridgeInterface, OvsBridgeOptions, OvsBridgePortConfig,
    OvsBridgeStpOptions, OvsDpdkConfig, OvsInterface, OvsPatchConfig,
};
pub(crate) use sriov::parse_sriov_vf_naming;
pub use sriov::{SrIovConfig, SrIovVfConfig};
pub use vlan::{
    VlanConfig, VlanInterface, VlanProtocol, VlanQosMapping,
    VlanRegistrationProtocol,
};
pub use vrf::{VrfConfig, VrfInterface};
pub use vxlan::{VxlanConfig, VxlanInterface};

#[cfg(test)]
// The pub(crate) re-export is only for unit tests (see
// unit_tests/ethtool.rs).
pub(crate) use self::ethtool::ETHTOOL_FEATURE_CLI_ALIAS;
pub(crate) use self::inter_ifaces::MergedInterfaces;
pub use self::{
    alt_name::{AltNameEntry, AltNameState},
    xfrm::XfrmInterface,
};
