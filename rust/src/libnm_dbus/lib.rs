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

mod active_connection;
mod connection;
mod convert;
mod dbus;
mod dbus_proxy;
mod device;
mod dns;
mod error;
mod keyfile;
mod nm_api;

pub use crate::active_connection::NmActiveConnection;
pub use crate::connection::{
    NmConnection, NmIpRoute, NmIpRouteRule, NmSettingBond, NmSettingBridge,
    NmSettingBridgeVlanRange, NmSettingConnection, NmSettingIp,
    NmSettingIpMethod, NmSettingMacVlan, NmSettingOvsBridge,
    NmSettingOvsExtIds, NmSettingOvsIface, NmSettingOvsPort, NmSettingSriov,
    NmSettingSriovVf, NmSettingSriovVfVlan, NmSettingVeth, NmSettingVlan,
    NmSettingVrf, NmSettingVxlan, NmSettingWired, NmVlanProtocol,
};
pub use crate::device::{NmDevice, NmDeviceState, NmDeviceStateReason};
pub use crate::dns::NmDnsEntry;
pub use crate::error::{ErrorKind, NmError};
pub use crate::nm_api::NmApi;
