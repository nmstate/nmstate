// SPDX-License-Identifier: Apache-2.0

use crate::{
    EthernetConfig, EthernetInterface, InterfaceType, Interfaces, NmstateError,
    VethConfig,
};

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

    pub(crate) fn pre_verify_cleanup(
        &mut self,
        pre_apply_current: Option<&Self>,
    ) {
        if let Some(eth_conf) = self.ethernet.as_mut() {
            eth_conf.pre_verify_cleanup(
                pre_apply_current.and_then(|c| c.ethernet.as_ref()),
            )
        }
        if self.base.iface_type == InterfaceType::Ethernet {
            self.veth = None;
        } else {
            self.base.iface_type = InterfaceType::Ethernet;
        }
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

impl EthernetConfig {
    pub(crate) fn update(&mut self, other: Option<&EthernetConfig>) {
        if let Some(other) = other {
            if let Some(sr_iov_conf) = &mut self.sr_iov {
                sr_iov_conf.update(other.sr_iov.as_ref())
            } else {
                self.sr_iov = other.sr_iov.clone()
            }
        }
    }

    pub(crate) fn pre_verify_cleanup(
        &mut self,
        pre_apply_current: Option<&Self>,
    ) {
        if self.auto_neg == Some(true) {
            self.speed = None;
            self.duplex = None;
        }
        if let Some(sriov_conf) = self.sr_iov.as_mut() {
            sriov_conf.pre_verify_cleanup(
                pre_apply_current.and_then(|c| c.sr_iov.as_ref()),
            )
        }
    }
}

impl VethConfig {
    fn update(&mut self, other: Option<&VethConfig>) {
        if let Some(other) = other {
            self.peer = other.peer.clone();
        }
    }
}
