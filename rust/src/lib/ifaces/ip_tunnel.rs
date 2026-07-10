// SPDX-License-Identifier: Apache-2.0

use std::net::IpAddr;

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, ErrorKind, InterfaceType, NmstateError};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
/// IP Tunnel interface. The example YAML output of a
/// [crate::NetworkState] with an ipip interface would be:
/// ```yaml
/// ---
/// interfaces:
///   - name: ipip0
///     type: ip-tunnel
///     state: up
///     ip-tunnel:
///       type: ipip
///       local: 192.0.2.1
///       remote: 192.0.2.2
///       ttl: 255
/// ```
pub struct IpTunnelInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Deserialize and serialize to `ip-tunnel`.
    pub ip_tunnel: Option<IpTunnelConfig>,
}

impl Default for IpTunnelInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::IpTunnel,
                ..Default::default()
            },
            ip_tunnel: None,
        }
    }
}

impl IpTunnelInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn sanitize(
        &mut self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if is_desired
            && let Some(conf) = &mut self.ip_tunnel
            && let Some(flow_label) = conf.flow_label
            && flow_label > 0xFFFFF
        {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                "Flow label must be less than 0xFFFFF".to_string(),
            ));
        }

        Ok(())
    }
}

#[derive(
    Serialize, Deserialize, Debug, Default, PartialEq, Eq, Clone, Copy,
)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum IpTunnelMode {
    #[default]
    Unknown,
    Ipip,
    Sit,
    Ip6ip6,
    Ipip6,
}

#[derive(
    Serialize, Deserialize, Debug, PartialEq, Eq, PartialOrd, Ord, Clone, Copy,
)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum Ip6TunnelFlag {
    IgnEncapLimit,
    UseOrigTclass,
    UseOrigFlowlabel,
    Mip6Dev,
    RcvDscpCopy,
    UseOrigFwMark,
    AllowLocalRemote,
    CapXmit,
    CapRcv,
    CapPerPacket,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
#[derive(Default)]
pub struct IpTunnelConfig {
    /// The mode of the IP tunnel.
    pub mode: Option<IpTunnelMode>,

    /// The parent interface name of the IP tunnel.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub base_iface: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub local: Option<IpAddr>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub remote: Option<IpAddr>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub ttl: Option<u8>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub tos: Option<u8>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub flow_label: Option<u32>,

    /// The flags of a ipip6 or ip6ip6 tunnel.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ip6tun_flags: Option<Vec<Ip6TunnelFlag>>,

    /// The PMTU discovery flag of the IP tunnel.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pmtu_disc: Option<bool>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub encap_limit: Option<u8>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub fwmark: Option<u32>,
}
