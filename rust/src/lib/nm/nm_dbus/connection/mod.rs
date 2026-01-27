// SPDX-License-Identifier: Apache-2.0

// Copyright 2021 Red Hat, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

#[macro_use]
mod macros;

mod bond;
mod bridge;
mod conn;
mod dns;
mod ethtool;
mod hsr;
mod ieee8021x;
mod iface_match;
mod iface_type;
mod infiniband;
mod ip;
mod ip_tunnel;
mod ipvlan;
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

pub(crate) use self::conn::{DBUS_ASV_SIGNATURE, DbusDictionary};
#[cfg(feature = "query_apply")]
pub(crate) use self::conn::{NmConnectionDbusValue, nm_con_get_from_obj_path};
#[cfg(feature = "query_apply")]
pub(crate) use self::macros::_from_map;
pub use self::{
    bond::{NmSettingBond, NmSettingBondPort},
    bridge::{NmSettingBridge, NmSettingBridgePort, NmSettingBridgeVlanRange},
    conn::{
        NmConnection, NmConnectionMultiConnect, NmRange, NmSettingConnection,
        NmSettingsConnectionFlag,
    },
    ethtool::NmSettingEthtool,
    hsr::NmSettingHsr,
    ieee8021x::NmSetting8021X,
    iface_match::NmSettingMatch,
    iface_type::NmIfaceType,
    infiniband::NmSettingInfiniBand,
    ip::{NmSettingIp, NmSettingIpMethod},
    ip_tunnel::{NmSettingIpTunnel, NmSettingIpTunnelFlag},
    ipvlan::NmSettingIpVlan,
    loopback::NmSettingLoopback,
    mac_vlan::NmSettingMacVlan,
    macsec::NmSettingMacSec,
    ovs::{
        NmSettingOvsBridge, NmSettingOvsDpdk, NmSettingOvsExtIds,
        NmSettingOvsIface, NmSettingOvsOtherConfig, NmSettingOvsPatch,
        NmSettingOvsPort,
    },
    route::NmIpRoute,
    route_rule::{NmIpRouteRule, NmIpRouteRuleAction},
    sriov::{NmSettingSriov, NmSettingSriovVf, NmSettingSriovVfVlan},
    user::NmSettingUser,
    veth::NmSettingVeth,
    vlan::{NmSettingVlan, NmSettingVlanFlag, NmVlanProtocol},
    vpn::NmSettingVpn,
    vrf::NmSettingVrf,
    vxlan::NmSettingVxlan,
    wired::NmSettingWired,
};
