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
mod ip;
mod mac_vlan;
mod ovs;
mod route;
mod route_rule;
mod sriov;
mod veth;
mod vlan;
mod vrf;
mod vxlan;
mod wired;

pub use crate::connection::bond::NmSettingBond;
pub use crate::connection::bridge::{
    NmSettingBridge, NmSettingBridgePort, NmSettingBridgeVlanRange,
};
pub use crate::connection::conn::{NmConnection, NmSettingConnection};
pub use crate::connection::ip::{NmSettingIp, NmSettingIpMethod};
pub use crate::connection::mac_vlan::NmSettingMacVlan;
pub use crate::connection::ovs::{
    NmSettingOvsBridge, NmSettingOvsExtIds, NmSettingOvsIface, NmSettingOvsPort,
};
pub use crate::connection::route::NmIpRoute;
pub use crate::connection::route_rule::NmIpRouteRule;
pub use crate::connection::sriov::{
    NmSettingSriov, NmSettingSriovVf, NmSettingSriovVfVlan,
};
pub use crate::connection::veth::NmSettingVeth;
pub use crate::connection::vlan::{NmSettingVlan, NmVlanProtocol};
pub use crate::connection::vrf::NmSettingVrf;
pub use crate::connection::vxlan::NmSettingVxlan;
pub use crate::connection::wired::NmSettingWired;

pub(crate) use crate::connection::conn::{
    nm_con_get_from_obj_path, DbusDictionary, NmConnectionDbusValue,
};
pub(crate) use crate::connection::macros::_from_map;
