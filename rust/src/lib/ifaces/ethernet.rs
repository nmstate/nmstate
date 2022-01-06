use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, InterfaceType, Interfaces, NmstateError, SrIovConfig,
};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
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
    pub(crate) fn update_ethernet(&mut self, other: &EthernetInterface) {
        if let Some(eth_conf) = &mut self.ethernet {
            eth_conf.update(other.ethernet.as_ref())
        } else {
            self.ethernet = other.ethernet.clone()
        }
    }

    pub(crate) fn update_veth(&mut self, other: &EthernetInterface) {
        if let Some(veth_conf) = &mut self.veth {
            veth_conf.update(other.veth.as_ref());
        } else {
            self.veth = other.veth.clone();
        }
    }

    pub(crate) fn pre_verify_cleanup(&mut self) {
        if let Some(eth_conf) = self.ethernet.as_mut() {
            eth_conf.pre_verify_cleanup()
        }
        self.base.iface_type = InterfaceType::Ethernet;
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

    pub(crate) fn verify_sriov(
        &self,
        cur_ifaces: &Interfaces,
    ) -> Result<(), NmstateError> {
        if let Some(eth_conf) = &self.ethernet {
            if let Some(sriov_conf) = &eth_conf.sr_iov {
                sriov_conf.verify_sriov(self.base.name.as_str(), cur_ifaces)?;
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
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

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub struct EthernetConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sr_iov: Option<SrIovConfig>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "auto-negotiation"
    )]
    pub auto_neg: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speed: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duplex: Option<EthernetDuplex>,
}

impl EthernetConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn update(&mut self, other: Option<&EthernetConfig>) {
        if let Some(other) = other {
            if let Some(sr_iov_conf) = &mut self.sr_iov {
                sr_iov_conf.update(other.sr_iov.as_ref())
            } else {
                self.sr_iov = other.sr_iov.clone()
            }
        }
    }

    pub(crate) fn pre_verify_cleanup(&mut self) {
        if self.auto_neg == Some(true) {
            self.speed = None;
            self.duplex = None;
        }
        if let Some(sriov_conf) = self.sr_iov.as_mut() {
            sriov_conf.pre_verify_cleanup()
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct VethConfig {
    pub peer: String,
}

impl VethConfig {
    fn update(&mut self, other: Option<&VethConfig>) {
        if let Some(other) = other {
            self.peer = other.peer.clone();
        }
    }
}
