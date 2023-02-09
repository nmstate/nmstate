// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, ErrorKind, Interface, InterfaceType, Interfaces,
    MergedInterfaces, NmstateError, SrIovConfig,
};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// Ethernet(IEEE 802.3) interface.
/// Besides [BaseInterface], optionally could hold [EthernetConfig] and/or
/// [VethConfig].
/// The yaml output of [crate::NetworkState] containing ethernet interface would
/// be:
/// ```yml
/// interfaces:
/// - name: ens3
///   type: ethernet
///   state: up
///   mac-address: 00:11:22:33:44:FF
///   mtu: 1500
///   min-mtu: 68
///   max-mtu: 65535
///   wait-ip: ipv4
///   ipv4:
///     enabled: true
///     dhcp: false
///     address:
///     - ip: 192.0.2.9
///       prefix-length: 24
///   ipv6:
///     enabled: false
///   mptcp:
///     address-flags: []
///   accept-all-mac-addresses: false
///   lldp:
///     enabled: false
///   ethtool:
///     feature:
///       tx-tcp-ecn-segmentation: true
///       tx-tcp-mangleid-segmentation: false
///       tx-tcp6-segmentation: true
///       tx-tcp-segmentation: true
///       rx-gro-list: false
///       rx-udp-gro-forwarding: false
///       rx-gro-hw: true
///       tx-checksum-ip-generic: true
///       tx-generic-segmentation: true
///       rx-gro: true
///       tx-nocache-copy: false
///     coalesce:
///       rx-frames: 1
///       tx-frames: 1
///     ring:
///       rx: 256
///       rx-max: 256
///       tx: 256
///       tx-max: 256
///   ethernet:
///     auto-negotiation: false
/// ```
pub struct EthernetInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ethernet: Option<EthernetConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// When applying, the [VethConfig] is only valid when
    /// [BaseInterface.iface_type] is set to [InterfaceType::Veth] explicitly.
    pub veth: Option<VethConfig>,
}

impl Default for EthernetInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::Ethernet;
        Self {
            base,
            ethernet: None,
            veth: None,
        }
    }
}

impl EthernetInterface {
    pub(crate) fn sanitize(&mut self) -> Result<(), NmstateError> {
        // Always set interface type to ethernet for verifying and applying
        self.base.iface_type = InterfaceType::Ethernet;

        if let Some(sriov_conf) =
            self.ethernet.as_mut().and_then(|e| e.sr_iov.as_mut())
        {
            sriov_conf.sanitize();
        }

        Ok(())
    }

    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum EthernetDuplex {
    /// Deserialize and serialize from/to `full`.
    Full,
    /// Deserialize and serialize from/to `half`.
    Half,
}

impl std::fmt::Display for EthernetDuplex {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Full => "full",
                Self::Half => "half",
            }
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct EthernetConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Single Root I/O Virtualization(SRIOV) configuration.
    /// Deserialize and serialize from/to `sr-iov`.
    pub sr_iov: Option<SrIovConfig>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "auto-negotiation",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    /// Deserialize and serialize from/to `auto-negotiation`.
    pub auto_neg: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub speed: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duplex: Option<EthernetDuplex>,
}

impl EthernetConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[non_exhaustive]
pub struct VethConfig {
    /// The name of veth peer.
    pub peer: String,
}

impl MergedInterfaces {
    pub(crate) fn has_sriov_vf_changes(&self) -> bool {
        self.kernel_ifaces.values().any(|i| {
            if let Some(Interface::Ethernet(eth_iface)) = i.for_apply.as_ref() {
                eth_iface.ethernet.as_ref().map(|e| e.sr_iov.is_some())
                    == Some(true)
            } else {
                false
            }
        })
    }

    // Raise error if new veth interface has no peer defined.
    // Mark old veth peer as absent when veth changed its peer.
    // Mark veth peer as absent also when veth is marked as absent.
    pub(crate) fn process_veth_peer_changes(
        &mut self,
    ) -> Result<(), NmstateError> {
        let mut veth_peers: Vec<&str> = Vec::new();
        for iface in self.iter().filter(|i| {
            i.merged.iface_type() == InterfaceType::Ethernet && i.merged.is_up()
        }) {
            if let Interface::Ethernet(eth_iface) = &iface.merged {
                if let Some(v) =
                    eth_iface.veth.as_ref().map(|v| v.peer.as_str())
                {
                    veth_peers.push(v);
                }
            }
        }
        for iface in self.iter().filter(|i| {
            i.merged.iface_type() == InterfaceType::Ethernet
                && i.is_desired()
                && i.current.is_none()
                && i.merged.is_up()
        }) {
            if let Some(Interface::Ethernet(eth_iface)) = &iface.desired {
                if eth_iface.veth.is_none()
                    && !self.gen_conf_mode
                    && !veth_peers.contains(&eth_iface.base.name.as_str())
                    && !self.has_sriov_vf_changes()
                {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Ethernet interface {} does not exists",
                            eth_iface.base.name.as_str()
                        ),
                    ));
                }
            }
        }

        let mut pending_deletions: Vec<String> = Vec::new();

        for iface in self.iter().filter(|i| {
            i.merged.iface_type() == InterfaceType::Ethernet
                && i.is_desired()
                && i.merged.is_up()
                && i.current.is_some()
        }) {
            if let (
                Some(Interface::Ethernet(des_eth_iface)),
                Some(Interface::Ethernet(cur_eth_iface)),
            ) = (iface.desired.as_ref(), iface.current.as_ref())
            {
                if let (Some(veth_conf), Some(cur_veth_conf)) =
                    (des_eth_iface.veth.as_ref(), cur_eth_iface.veth.as_ref())
                {
                    if veth_conf.peer != cur_veth_conf.peer {
                        pending_deletions.push(cur_veth_conf.peer.to_string());
                    }
                }
            }
        }

        for iface in self.iter().filter(|i| {
            i.merged.iface_type() == InterfaceType::Ethernet
                && i.is_desired()
                && i.merged.is_absent()
                && i.current.is_some()
        }) {
            if let Some(Interface::Ethernet(cur_eth_iface)) =
                iface.current.as_ref()
            {
                if let Some(veth_conf) = cur_eth_iface.veth.as_ref() {
                    pending_deletions.push(veth_conf.peer.to_string());
                }
            }
        }

        for del_peer in pending_deletions {
            if let Some(iface) = self.kernel_ifaces.get_mut(&del_peer) {
                iface.mark_as_absent();
            }
        }
        Ok(())
    }
}

impl Interfaces {
    // Not allowing changing veth peer away from ignored peer unless previous
    // peer changed from ignore to managed
    pub(crate) fn validate_change_veth_ignored_peer(
        &self,
        current: &Self,
        ignored_ifaces: &[(String, InterfaceType)],
    ) -> Result<(), NmstateError> {
        let ignored_veth_ifaces: Vec<&String> = ignored_ifaces
            .iter()
            .filter_map(|(n, t)| {
                if t == &InterfaceType::Ethernet {
                    Some(n)
                } else {
                    None
                }
            })
            .collect();

        for iface in self.kernel_ifaces.values().filter(|i| {
            if let Interface::Ethernet(i) = i {
                i.veth.is_some()
            } else {
                false
            }
        }) {
            if let (
                Interface::Ethernet(des_iface),
                Some(Interface::Ethernet(cur_iface)),
            ) = (iface, current.get_iface(iface.name(), InterfaceType::Veth))
            {
                if let (Some(des_peer), cur_peer) = (
                    des_iface.veth.as_ref().map(|v| v.peer.as_str()),
                    cur_iface.veth.as_ref().map(|v| v.peer.as_str()),
                ) {
                    let cur_peer = if let Some(c) = cur_peer {
                        c
                    } else {
                        // The veth peer is in another namespace.
                        let e = NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Veth interface {} is currently holding \
                                peer assigned to other namespace \
                                Please remove this veth pair \
                                before changing veth peer to {des_peer}",
                                iface.name(),
                            ),
                        );
                        log::error!("{}", e);
                        return Err(e);
                    };

                    if des_peer != cur_peer
                        && ignored_veth_ifaces.contains(&&cur_peer.to_string())
                    {
                        let e = NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Veth interface {} is currently holding \
                                peer {} which is marked as ignored. \
                                Hence not allowing changing its peer \
                                to {}. Please remove this veth pair \
                                before changing veth peer",
                                iface.name(),
                                cur_peer,
                                des_peer
                            ),
                        );
                        log::error!("{}", e);
                        return Err(e);
                    }
                }
            }
        }
        Ok(())
    }

    pub(crate) fn validate_new_veth_without_peer(
        &self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        for iface in self.kernel_ifaces.values().filter(|i| {
            i.is_up()
                && i.iface_type() == InterfaceType::Veth
                && current.kernel_ifaces.get(i.name()).is_none()
        }) {
            if let Interface::Ethernet(eth_iface) = iface {
                if eth_iface.veth.is_none() {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Veth interface {} does not exist, \
                            peer name is required for creating it",
                            iface.name()
                        ),
                    ));
                }
            }
        }
        Ok(())
    }
}
