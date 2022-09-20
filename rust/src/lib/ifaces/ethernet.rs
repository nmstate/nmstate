use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, ErrorKind, Interface, InterfaceState, InterfaceType,
    Interfaces, NmstateError, SrIovConfig,
};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct EthernetInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ethernet: Option<EthernetConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
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
    pub(crate) fn pre_edit_cleanup(&mut self) -> Result<(), NmstateError> {
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
            Err(e)
        } else {
            Ok(())
        }
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
    Full,
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
    pub sr_iov: Option<SrIovConfig>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "auto-negotiation",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
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
