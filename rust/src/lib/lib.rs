// SPDX-License-Identifier: Apache-2.0

mod deserializer;
mod dns;
mod error;
#[cfg(feature = "gen_conf")]
mod gen_conf;
mod hostname;
mod ieee8021x;
mod iface;
mod ifaces;
mod ip;
mod lldp;
mod mptcp;
mod net_state;
#[cfg(feature = "query_apply")]
mod nispor;
mod nm;
mod ovs;
#[cfg(feature = "query_apply")]
mod ovsdb;
#[cfg(feature = "query_apply")]
mod query_apply;
mod route;
mod route_rule;
mod serializer;
#[cfg(feature = "query_apply")]
mod state;
mod unit_tests;

pub use crate::dns::{DnsClientState, DnsState};
pub use crate::error::{ErrorKind, NmstateError};
pub use crate::hostname::HostNameState;
pub use crate::ieee8021x::Ieee8021XConfig;
pub use crate::iface::{
    Interface, InterfaceState, InterfaceType, UnknownInterface,
};
pub use crate::ifaces::{
    BaseInterface, BondAdSelect, BondAllPortsActive, BondArpAllTargets,
    BondArpValidate, BondConfig, BondFailOverMac, BondInterface, BondLacpRate,
    BondMode, BondOptions, BondPrimaryReselect, BondXmitHashPolicy,
    BridgePortTunkTag, BridgePortVlanConfig, BridgePortVlanMode,
    BridgePortVlanRange, DummyInterface, EthernetConfig, EthernetDuplex,
    EthernetInterface, EthtoolCoalesceConfig, EthtoolConfig,
    EthtoolFeatureConfig, EthtoolPauseConfig, EthtoolRingConfig,
    InfiniBandConfig, InfiniBandInterface, InfiniBandMode, Interfaces,
    LinuxBridgeConfig, LinuxBridgeInterface, LinuxBridgeMulticastRouterType,
    LinuxBridgeOptions, LinuxBridgePortConfig, LinuxBridgeStpOptions,
    MacVlanConfig, MacVlanInterface, MacVlanMode, MacVtapConfig,
    MacVtapInterface, MacVtapMode, OvsBridgeBondConfig, OvsBridgeBondMode,
    OvsBridgeBondPortConfig, OvsBridgeConfig, OvsBridgeInterface,
    OvsBridgeOptions, OvsBridgePortConfig, OvsDpdkConfig, OvsInterface,
    OvsPatchConfig, SrIovConfig, SrIovVfConfig, VethConfig, VlanConfig,
    VlanInterface, VlanProtocol, VrfConfig, VrfInterface, VxlanConfig,
    VxlanInterface,
};
pub use crate::ip::{
    Dhcpv4ClientId, Dhcpv6Duid, InterfaceIpAddr, InterfaceIpv4, InterfaceIpv6,
    Ipv6AddrGenMode, WaitIp,
};
pub use crate::lldp::{
    LldpAddressFamily, LldpChassisId, LldpChassisIdType, LldpConfig,
    LldpMacPhyConf, LldpMaxFrameSize, LldpMgmtAddr, LldpMgmtAddrs,
    LldpNeighborTlv, LldpPortId, LldpPortIdType, LldpPpvids,
    LldpSystemCapabilities, LldpSystemCapability, LldpSystemDescription,
    LldpSystemName, LldpVlan, LldpVlans,
};
pub use crate::mptcp::{MptcpAddressFlag, MptcpConfig};
pub use crate::net_state::NetworkState;
pub use crate::ovs::{OvsDbGlobalConfig, OvsDbIfaceConfig};
pub use crate::route::{RouteEntry, RouteState, Routes};
pub use crate::route_rule::{RouteRuleEntry, RouteRuleState, RouteRules};
