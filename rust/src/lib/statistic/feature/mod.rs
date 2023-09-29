// SPDX-License-Identifier: Apache-2.0

mod dns;
mod ethernet;
mod hostname;
mod iface;
mod inter_ifaces;
mod ip;
mod ovs;
mod route;
mod route_rule;

use serde::Serialize;

#[derive(Clone, Copy, Hash, Debug, Serialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum NmstateFeature {
    StaticDnsNameServer,
    StaticDnsSearch,
    StaticDnsOption,
    StaticRoute,
    StaticRouteRule,
    StaticHostname,
    Sriov,
    OvsDpdk,
    OvsBond,
    OvsDbGlobal,
    OvsDbInterface,
    OvnMapping,
    MacBasedIdentifier,
}
