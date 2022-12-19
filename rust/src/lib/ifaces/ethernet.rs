use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, ErrorKind, Interface, InterfaceState, InterfaceType,
    Interfaces, NmstateError, SrIovConfig,
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
    pub(crate) fn pre_edit_cleanup(
        &mut self,
        current: Option<&Self>,
    ) -> Result<(), NmstateError> {
        if self.base.iface_type != InterfaceType::Veth && self.veth.is_some() {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Interface {} is holding veth configuration \
                    with `type: ethernet`. Please change to `type: veth`",
                    self.base.name.as_str()
                ),
            );
            log::error!("{}", e);
            return Err(e);
        }
        if let Some(eth_conf) = self.ethernet.as_mut() {
            eth_conf
                .pre_edit_cleanup(current.and_then(|c| c.ethernet.as_ref()));
        }
        Ok(())
    }

    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn sriov_is_enabled(&self) -> bool {
        self.ethernet
            .as_ref()
            .and_then(|eth_conf| {
                eth_conf.sr_iov.as_ref().map(SrIovConfig::sriov_is_enabled)
            })
            .unwrap_or_default()
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

    pub(crate) fn pre_edit_cleanup(&mut self, current: Option<&Self>) {
        if let Some(sriov_conf) = self.sr_iov.as_mut() {
            sriov_conf
                .pre_edit_cleanup(current.and_then(|c| c.sr_iov.as_ref()));
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[non_exhaustive]
pub struct VethConfig {
    /// The name of veth peer.
    pub peer: String,
}

// Raise error if new veth interface has no peer defined.
// Mark old veth peer as absent when veth changed its peer.
// Mark veth peer as absent also when veth is marked as absent.
pub(crate) fn handle_veth_peer_changes(
    add_ifaces: &Interfaces,
    chg_ifaces: &mut Interfaces,
    del_ifaces: &mut Interfaces,
    current: &Interfaces,
) -> Result<(), NmstateError> {
    for iface in add_ifaces
        .kernel_ifaces
        .values()
        .filter(|i| i.iface_type() == InterfaceType::Veth)
    {
        if let Interface::Ethernet(eth_iface) = iface {
            if eth_iface.veth.is_none() {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Veth interface {} does not exists, \
                        peer name is required for creating it",
                        iface.name()
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
    }
    for (iface_name, iface) in chg_ifaces.kernel_ifaces.iter() {
        if let Interface::Ethernet(eth_iface) = iface {
            let cur_eth_iface = if let Some(Interface::Ethernet(i)) =
                current.kernel_ifaces.get(iface_name)
            {
                i
            } else {
                continue;
            };
            if let (Some(veth_conf), Some(cur_veth_conf)) =
                (eth_iface.veth.as_ref(), cur_eth_iface.veth.as_ref())
            {
                if veth_conf.peer != cur_veth_conf.peer {
                    del_ifaces.push(new_absent_eth_iface(
                        cur_veth_conf.peer.as_str(),
                    ));
                }
            }
        }
    }

    for iface in chg_ifaces.kernel_ifaces.values_mut() {
        if iface.iface_type() == InterfaceType::Veth {
            if let Interface::Ethernet(eth_iface) = iface {
                if eth_iface.veth.is_none() {
                    eth_iface.base.iface_type = InterfaceType::Ethernet;
                }
            }
        }
    }

    let mut del_peers: Vec<&str> = Vec::new();
    for iface in del_ifaces
        .kernel_ifaces
        .values()
        .filter(|i| matches!(i, Interface::Ethernet(_)))
    {
        if let Some(Interface::Ethernet(cur_eth_iface)) =
            current.kernel_ifaces.get(iface.name())
        {
            if let Some(veth_conf) = cur_eth_iface.veth.as_ref() {
                del_peers.push(veth_conf.peer.as_str());
            }
        }
    }
    for del_peer in del_peers {
        if !del_ifaces.kernel_ifaces.contains_key(del_peer) {
            del_ifaces.push(new_absent_eth_iface(del_peer));
        }
    }
    Ok(())
}

fn new_absent_eth_iface(name: &str) -> Interface {
    let mut iface = EthernetInterface::new();
    iface.base = BaseInterface {
        name: name.to_string(),
        iface_type: InterfaceType::Ethernet,
        state: InterfaceState::Absent,
        ..Default::default()
    };
    Interface::Ethernet(iface)
}
