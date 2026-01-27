// SPDX-License-Identifier: Apache-2.0

use crate::{
    BaseInterface, ErrorKind, IpTunnelMode, NmstateError,
    ifaces::{Ip6TunnelFlag, IpTunnelConfig, IpTunnelInterface},
};

fn np_ip6tun_flags_to_nmstate(
    flags: &[nispor::Ip6TunnelFlag],
) -> Vec<Ip6TunnelFlag> {
    flags
        .iter()
        .filter_map(|&flag| {
            Ip6TunnelFlag::try_from(flag)
                .map_err(|_| {
                    log::warn!("Unknown ip6tun flag: {flag:?}, skipping")
                })
                .ok()
        })
        .collect()
}

const IPV6_FLOWLABEL_MASK: u32 = 0x000FFFFF;

pub(crate) fn np_ip_tunnel_to_nmstate(
    np_iface: &nispor::Iface,
    base_iface: BaseInterface,
) -> IpTunnelInterface {
    let ip_tunnel_conf =
        np_iface
            .ip_tunnel
            .as_ref()
            .map(|np_ip_tunnel_info| IpTunnelConfig {
                mode: Some(np_ip_tunnel_info.mode.into()),
                base_iface: np_ip_tunnel_info.parent.clone(),
                local: np_ip_tunnel_info.local,
                remote: np_ip_tunnel_info.remote,
                ttl: np_ip_tunnel_info.ttl,
                tos: np_ip_tunnel_info.tos,
                flow_label: np_ip_tunnel_info.flow_info.map(|flow_info| {
                    u32::from_be(flow_info) & IPV6_FLOWLABEL_MASK
                }),
                ip6tun_flags: np_ip_tunnel_info
                    .ip6tun_flags
                    .as_deref()
                    .map(np_ip6tun_flags_to_nmstate),
                pmtu_disc: np_ip_tunnel_info.pmtu_disc,
                encap_limit: np_ip_tunnel_info.encap_limit,
                fwmark: np_ip_tunnel_info.fwmark,
            });

    IpTunnelInterface {
        base: base_iface,
        ip_tunnel: ip_tunnel_conf,
    }
}

impl std::convert::TryFrom<nispor::Ip6TunnelFlag> for Ip6TunnelFlag {
    type Error = NmstateError;
    fn try_from(flag: nispor::Ip6TunnelFlag) -> Result<Self, NmstateError> {
        match flag {
            nispor::Ip6TunnelFlag::IgnEncapLimit => Ok(Self::IgnEncapLimit),
            nispor::Ip6TunnelFlag::UseOrigTclass => Ok(Self::UseOrigTclass),
            nispor::Ip6TunnelFlag::UseOrigFlowlabel => {
                Ok(Self::UseOrigFlowlabel)
            }
            nispor::Ip6TunnelFlag::Mip6Dev => Ok(Self::Mip6Dev),
            nispor::Ip6TunnelFlag::RcvDscpCopy => Ok(Self::RcvDscpCopy),
            nispor::Ip6TunnelFlag::UseOrigFwMark => Ok(Self::UseOrigFwMark),
            nispor::Ip6TunnelFlag::AllowLocalRemote => {
                Ok(Self::AllowLocalRemote)
            }
            nispor::Ip6TunnelFlag::CapXmit => Ok(Self::CapXmit),
            nispor::Ip6TunnelFlag::CapRcv => Ok(Self::CapRcv),
            nispor::Ip6TunnelFlag::CapPerPacket => Ok(Self::CapPerPacket),
            _ => Err(NmstateError::new(
                ErrorKind::NotSupportedError,
                format!("Unknown IP6 tunnel flag: {flag:?}"),
            )),
        }
    }
}

impl From<nispor::IpTunnelMode> for IpTunnelMode {
    fn from(mode: nispor::IpTunnelMode) -> Self {
        match mode {
            nispor::IpTunnelMode::Ipip => IpTunnelMode::Ipip,
            nispor::IpTunnelMode::Sit => IpTunnelMode::Sit,
            nispor::IpTunnelMode::Ip6ip6 => IpTunnelMode::Ip6ip6,
            nispor::IpTunnelMode::Ipip6 => IpTunnelMode::Ipip6,
            _ => {
                log::warn!("Unknown IP tunnel mode: {mode:?}");
                Self::default()
            }
        }
    }
}
