// SPDX-License-Identifier: Apache-2.0

#![doc(html_favicon_url = "https://nmstate.io/favicon.png")]
#![doc(html_logo_url = "https://nmstate.io/favicon.png")]

//! Declarative API for Host Network Management
//! Nmstate is a library with an accompanying command line tool that manages
//! host networking settings in a declarative manner. The networking state is
//! described by a pre-defined schema. Reporting of current state and changes to
//! it (desired state) both conform to the schema.
//!
//! Nmstate is aimed to satisfy enterprise needs to manage host networking
//! through a northbound declarative API and multi provider support on the
//! southbound. NetworkManager acts as the main provider supported to provide
//! persistent network configuration after reboot. Kernel mode is also provided
//! as tech-preview to apply network configurations without NetworkManager.
//!
//! The [NetworkState] and its subordinates are all implemented the serde
//! `Deserialize` and  `Serialize`, instead of building up [NetworkState]
//! manually, you may deserialize it from file(e.g. JSON, YAML and etc).
//!
//! ## Features
//! The `nmstate` crate has these cargo features:
//!  * `gen_conf` -- Generate offline network configures.
//!  * `query_apply` -- Query and apply network state.
//!
//! By default, both features are enabled.
//! The `gen_conf` feature is only supported on Linux platform.
//! The `query_apply` feature is supported and tested on both Linux and MacOS.
//!
//! ## Examples
//!
//! To retrieve current network state:
//!
//! ```no_run
//! use nmstate::NetworkState;
//!
//! fn main() -> Result<(), Box<dyn std::error::Error>> {
//!     let mut net_state = NetworkState::new();
//!     // Use kernel mode
//!     net_state.set_kernel_only(true);
//!     net_state.retrieve()?;
//!     println!("{}", serde_yaml::to_string(&net_state)?);
//!     Ok(())
//! }
//! ```
//!
//! To apply network configuration(e.g. Assign static IP to eth1):
//!
//! ```no_run
//! use nmstate::NetworkState;
//!
//! fn main() -> Result<(), Box<dyn std::error::Error>> {
//!     let mut net_state: NetworkState = serde_yaml::from_str(
//!         r#"---
//!         interfaces:
//!           - name: eth1
//!             type: ethernet
//!             state: up
//!             mtu: 1500
//!             ipv4:
//!               address:
//!               - ip: 192.0.2.252
//!                 prefix-length: 24
//!               - ip: 192.0.2.251
//!                 prefix-length: 24
//!               dhcp: false
//!               enabled: true
//!             ipv6:
//!               address:
//!                 - ip: 2001:db8:2::1
//!                   prefix-length: 64
//!                 - ip: 2001:db8:1::1
//!                   prefix-length: 64
//!               autoconf: false
//!               dhcp: false
//!               enabled: true
//!         "#,
//!     )?;
//!     net_state.set_kernel_only(true);
//!     net_state.apply()?;
//!     Ok(())
//! }
//! ```

mod deserializer;
mod dispatch;
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
#[allow(deprecated)]
mod ovn;
mod ovs;
#[cfg(feature = "query_apply")]
mod ovsdb;
mod pci_address;
#[cfg(feature = "query_apply")]
mod policy;
#[cfg(feature = "query_apply")]
mod query_apply;
#[cfg(feature = "gen_revert")]
mod revert;
mod route;
mod route_rule;
mod serializer;
mod state;
#[cfg(feature = "query_apply")]
mod statistic;
mod unit_tests;
#[cfg(feature = "query_apply")]
mod validate;

#[cfg(feature = "query_apply")]
pub use crate::policy::{
    NetworkCaptureRules, NetworkPolicy, NetworkStateTemplate,
};
#[cfg(feature = "query_apply")]
pub use crate::statistic::{NmstateFeature, NmstateStatistic};
pub use crate::{
    dispatch::DispatchConfig,
    dns::{DnsClientState, DnsState},
    error::{ErrorKind, NmstateError},
    hostname::HostNameState,
    ieee8021x::Ieee8021XConfig,
    iface::{
        Interface, InterfaceIdentifier, InterfaceState, InterfaceType,
        UnknownInterface,
    },
    ifaces::{
        AltNameEntry, AltNameState, BaseInterface, BondAdSelect,
        BondAllPortsActive, BondArpAllTargets, BondArpValidate, BondConfig,
        BondFailOverMac, BondInterface, BondLacpRate, BondMode, BondOptions,
        BondPortConfig, BondPrimaryReselect, BondXmitHashPolicy,
        BridgePortTrunkTag, BridgePortVlanConfig, BridgePortVlanMode,
        BridgePortVlanRange, DummyInterface, EthernetConfig, EthernetDuplex,
        EthernetInterface, EthtoolCoalesceConfig, EthtoolConfig,
        EthtoolFeatureConfig, EthtoolFecConfig, EthtoolFecMode,
        EthtoolPauseConfig, EthtoolRingConfig, HsrConfig, HsrInterface,
        HsrProtocol, InfiniBandConfig, InfiniBandInterface, InfiniBandMode,
        Interfaces, IpVlanConfig, IpVlanInterface, IpVlanMode, IpsecInterface,
        LibreswanAddressFamily, LibreswanConfig, LibreswanConnectionType,
        LinuxBridgeConfig, LinuxBridgeInterface,
        LinuxBridgeMulticastRouterType, LinuxBridgeOptions,
        LinuxBridgePortConfig, LinuxBridgeStpOptions, LoopbackInterface,
        MacSecConfig, MacSecInterface, MacSecOffload, MacSecValidate,
        MacVlanConfig, MacVlanInterface, MacVlanMode, MacVtapConfig,
        MacVtapInterface, MacVtapMode, OvsBridgeBondConfig, OvsBridgeBondMode,
        OvsBridgeBondPortConfig, OvsBridgeConfig, OvsBridgeInterface,
        OvsBridgeOptions, OvsBridgePortConfig, OvsBridgeStpOptions,
        OvsDpdkConfig, OvsInterface, OvsPatchConfig, SrIovConfig,
        SrIovVfConfig, VethConfig, VlanConfig, VlanInterface, VlanProtocol,
        VlanQosMapping, VlanRegistrationProtocol, VrfConfig, VrfInterface,
        VxlanConfig, VxlanInterface, XfrmInterface,
    },
    ip::{
        AddressFamily, AddressProtocol, Dhcpv4ClientId, Dhcpv6Duid,
        InterfaceIpAddr, InterfaceIpv4, InterfaceIpv6, Ipv6AddrGenMode, WaitIp,
    },
    lldp::{
        LldpAddressFamily, LldpChassisId, LldpChassisIdType, LldpConfig,
        LldpMacPhy, LldpMaxFrameSize, LldpMgmtAddr, LldpMgmtAddrs,
        LldpNeighborTlv, LldpPortId, LldpPortIdType, LldpPpvids,
        LldpSystemCapabilities, LldpSystemCapability, LldpSystemDescription,
        LldpSystemName, LldpVlan, LldpVlans,
    },
    mptcp::{MptcpAddressFlag, MptcpConfig},
    net_state::NetworkState,
    ovn::{OvnBridgeMapping, OvnBridgeMappingState, OvnConfiguration},
    ovs::{OvsDbGlobalConfig, OvsDbIfaceConfig},
    pci_address::PciAddress,
    route::{RouteEntry, RouteState, RouteType, Routes},
    route_rule::{RouteRuleAction, RouteRuleEntry, RouteRuleState, RouteRules},
};
pub(crate) use crate::{
    dns::MergedDnsState,
    hostname::MergedHostNameState,
    iface::MergedInterface,
    ifaces::MergedInterfaces,
    net_state::{MergedNetworkState, NetworkStateMode},
    ovn::MergedOvnConfiguration,
    ovs::MergedOvsDbGlobalConfig,
    route::MergedRoutes,
    route_rule::MergedRouteRules,
};
