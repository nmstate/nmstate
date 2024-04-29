// SPDX-License-Identifier: Apache-2.0

#[macro_use]
mod macros;

mod bond;
mod bridge;
mod conn;
mod dns;
mod ethtool;
mod generic;
mod hsr;
mod ieee8021x;
mod infiniband;
mod ip;
mod loopback;
mod mac_vlan;
mod macsec;
mod ovs;
mod route;
mod route_rule;
mod sriov;
mod user;
mod veth;
mod vlan;
mod vpn;
mod vrf;
mod vxlan;
mod wired;

pub use self::bond::{NmSettingBond, NmSettingBondPort};
pub use self::bridge::{
    NmSettingBridge, NmSettingBridgePort, NmSettingBridgeVlanRange,
};
pub use self::conn::{
    NmConnection, NmRange, NmSettingConnection, NmSettingsConnectionFlag,
};
pub use self::ethtool::NmSettingEthtool;
pub use self::generic::NmSettingGeneric;
pub use self::hsr::NmSettingHsr;
pub use self::ieee8021x::NmSetting8021X;
pub use self::infiniband::NmSettingInfiniBand;
pub use self::ip::{NmSettingIp, NmSettingIpMethod};
pub use self::loopback::NmSettingLoopback;
pub use self::mac_vlan::NmSettingMacVlan;
pub use self::macsec::NmSettingMacSec;
pub use self::ovs::{
    NmSettingOvsBridge, NmSettingOvsDpdk, NmSettingOvsExtIds,
    NmSettingOvsIface, NmSettingOvsOtherConfig, NmSettingOvsPatch,
    NmSettingOvsPort,
};
pub use self::route::NmIpRoute;
pub use self::route_rule::{NmIpRouteRule, NmIpRouteRuleAction};
pub use self::sriov::{NmSettingSriov, NmSettingSriovVf, NmSettingSriovVfVlan};
pub use self::user::NmSettingUser;
pub use self::veth::NmSettingVeth;
pub use self::vlan::{NmSettingVlan, NmSettingVlanFlag, NmVlanProtocol};
pub use self::vpn::NmSettingVpn;
pub use self::vrf::NmSettingVrf;
pub use self::vxlan::NmSettingVxlan;
pub use self::wired::NmSettingWired;

pub(crate) use self::conn::DbusDictionary;
#[cfg(feature = "query_apply")]
pub(crate) use self::conn::{nm_con_get_from_obj_path, NmConnectionDbusValue};
#[cfg(feature = "query_apply")]
pub(crate) use self::macros::_from_map;
