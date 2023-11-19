// SPDX-License-Identifier: Apache-2.0

use serde::Serialize;

#[derive(
    Clone, Copy, Hash, Debug, Serialize, PartialEq, Eq, Ord, PartialOrd,
)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
// Please sort this list
pub enum NmstateFeature {
    Dhcpv4CustomHostname,
    Dhcpv6CustomHostname,
    IfaceNameReferedBySriovVfId,
    Lldp,
    MacBasedIdentifier,
    Mptcp,
    OvnMapping,
    OvsBond,
    OvsDbGlobal,
    OvsDbInterface,
    OvsDpdk,
    OvsPatch,
    Sriov,
    StaticDnsNameServer,
    StaticDnsOption,
    StaticDnsSearch,
    StaticHostname,
    StaticRoute,
    StaticRouteRule,
    StaticRouteRuleSuppressPrefixLength,
    IfaceCount10Plus,
    IfaceCount50Plus,
    IfaceCount100Plus,
    IfaceCount200Plus,
    IfaceCount500Plus,
}
