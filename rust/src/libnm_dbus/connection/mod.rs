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

mod bridge;
mod conn;
mod ip;
mod ovs;
mod wired;

pub use crate::connection::bridge::NmSettingBridge;
pub use crate::connection::conn::{NmConnection, NmSettingConnection};
pub use crate::connection::ip::{NmSettingIp, NmSettingIpMethod};
pub use crate::connection::ovs::{
    NmSettingOvsBridge, NmSettingOvsIface, NmSettingOvsPort,
};
pub use crate::connection::wired::NmSettingWired;

pub(crate) use crate::connection::conn::{
    nm_con_get_from_obj_path, NmConnectionDbusOwnedValue, NmConnectionDbusValue,
};
