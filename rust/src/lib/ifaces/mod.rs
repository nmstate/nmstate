// SPDX-License-Identifier: Apache-2.0

mod base;
mod bond;
mod bridge_vlan;
mod dummy;
mod ethernet;
mod ethtool;
mod hsr;
pub(crate) mod inter_ifaces;
mod ipsec;
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

pub use self::xfrm::XfrmInterface;
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
    EthtoolPauseConfig, EthtoolRingConfig,
};
pub use hsr::{HsrConfig, HsrInterface, HsrProtocol};
pub use infiniband::{InfiniBandConfig, InfiniBandInterface, InfiniBandMode};
pub(crate) use inter_ifaces::MergedInterfaces;
pub use inter_ifaces::*;
pub use ipsec::{
    IpsecInterface, LibreswanAddressFamily, LibreswanConfig,
    LibreswanConnectionType,
};
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
pub use sriov::{SrIovConfig, SrIovVfConfig};
pub use vlan::{
    VlanConfig, VlanInterface, VlanProtocol, VlanRegistrationProtocol,
};
pub use vrf::{VrfConfig, VrfInterface};
pub use vxlan::{VxlanConfig, VxlanInterface};
