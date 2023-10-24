// SPDX-License-Identifier: Apache-2.0

mod active_connection;
mod connection;
mod convert;
#[cfg(feature = "query_apply")]
mod dbus;
#[cfg(feature = "query_apply")]
mod dbus_proxy;
mod device;
#[cfg(feature = "query_apply")]
mod dns;
mod error;
#[cfg(feature = "query_apply")]
mod lldp;
#[cfg(feature = "query_apply")]
mod nm_api;

#[cfg(feature = "gen_conf")]
mod gen_conf;
#[cfg(feature = "query_apply")]
mod query_apply;

pub use self::active_connection::{
    NmActiveConnection, NM_ACTIVATION_STATE_FLAG_EXTERNAL,
};
pub use self::connection::{
    NmConnection, NmIpRoute, NmIpRouteRule, NmIpRouteRuleAction, NmRange,
    NmSetting8021X, NmSettingBond, NmSettingBondPort, NmSettingBridge,
    NmSettingBridgePort, NmSettingBridgeVlanRange, NmSettingConnection,
    NmSettingEthtool, NmSettingInfiniBand, NmSettingIp, NmSettingIpMethod,
    NmSettingMacVlan, NmSettingOvsBridge, NmSettingOvsDpdk, NmSettingOvsExtIds,
    NmSettingOvsIface, NmSettingOvsOtherConfig, NmSettingOvsPatch,
    NmSettingOvsPort, NmSettingSriov, NmSettingSriovVf, NmSettingSriovVfVlan,
    NmSettingUser, NmSettingVeth, NmSettingVlan, NmSettingVrf, NmSettingVxlan,
    NmSettingWired, NmSettingsConnectionFlag, NmVlanProtocol,
};
pub use self::device::{NmDevice, NmDeviceState, NmDeviceStateReason};
#[cfg(feature = "query_apply")]
pub use self::dns::{NmDnsEntry, NmGlobalDnsConfig};
pub use self::error::{
    ErrorKind, NmConnectionError, NmError, NmManagerError, NmSettingError,
};
#[cfg(feature = "query_apply")]
pub use self::lldp::{NmLldpNeighbor, NmLldpNeighbor8021Vlan};
#[cfg(feature = "query_apply")]
pub use self::nm_api::NmApi;

pub(crate) use self::convert::ToDbusValue;
#[cfg(feature = "gen_conf")]
pub(crate) use self::gen_conf::ToKeyfile;
