// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, EthernetConfig, EthernetInterface, Interface, Interfaces,
    NetworkState, NmstateError, SrIovConfig, VethConfig,
};

impl EthernetInterface {
    pub(crate) fn sriov_is_enabled(&self) -> bool {
        self.ethernet
            .as_ref()
            .and_then(|eth_conf| {
                eth_conf.sr_iov.as_ref().map(SrIovConfig::sriov_is_enabled)
            })
            .unwrap_or_default()
    }

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
}

impl VethConfig {
    fn update(&mut self, other: Option<&VethConfig>) {
        if let Some(other) = other {
            self.peer = other.peer.clone();
        }
    }
}

impl SrIovConfig {
    pub(crate) fn sriov_is_enabled(&self) -> bool {
        matches!(self.total_vfs, Some(i) if i > 0)
    }
}

// Checking existence of file:
//      /sys/class/net/<iface_name>/device/sriov_numvfs
fn is_sriov_supported(iface_name: &str) -> bool {
    let path = format!("/sys/class/net/{iface_name}/device/sriov_numvfs");
    std::path::Path::new(&path).exists()
}

impl Interfaces {
    pub(crate) fn check_sriov_capability(&self) -> Result<(), NmstateError> {
        for iface in self.kernel_ifaces.values() {
            if let Interface::Ethernet(eth_iface) = iface {
                if eth_iface.sriov_is_enabled()
                    && !is_sriov_supported(iface.name())
                {
                    let e = NmstateError::new(
                        ErrorKind::NotSupportedError,
                        format!(
                            "SR-IOV is not supported by interface {}",
                            iface.name()
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
        }
        Ok(())
    }
}

impl NetworkState {
    // Return newly create NetworkState containing only ethernet section of
    // interface with SR-IOV PF changes. The self will have the SR-IOV PF change
    // removed.
    pub(crate) fn isolate_sriov_conf_out(&mut self) -> Option<Self> {
        let mut pf_ifaces: Vec<Interface> = Vec::new();

        for iface in
            self.interfaces.kernel_ifaces.values_mut().filter_map(|i| {
                if i.is_up() {
                    if let Interface::Ethernet(iface) = i {
                        Some(iface)
                    } else {
                        None
                    }
                } else {
                    None
                }
            })
        {
            if let Some(true) =
                iface.ethernet.as_ref().map(|e| e.sr_iov.is_some())
            {
                if let Some(eth_conf) = iface.ethernet.as_ref() {
                    pf_ifaces.push(Interface::Ethernet(EthernetInterface {
                        base: iface.base.clone_name_type_only(),
                        ethernet: Some(eth_conf.clone()),
                        ..Default::default()
                    }));
                    iface.ethernet = None;
                }
            }
        }

        if pf_ifaces.is_empty() {
            None
        } else {
            let mut pf_state = NetworkState::default();
            for pf_iface in pf_ifaces {
                pf_state.interfaces.push(pf_iface);
            }
            Some(pf_state)
        }
    }
}
