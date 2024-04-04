// SPDX-License-Identifier: Apache-2.0

use std::collections::hash_map::Entry;

use crate::{
    BaseInterface, ErrorKind, EthernetConfig, EthernetInterface, Interface,
    InterfaceType, Interfaces, NmstateError, SrIovConfig, SrIovVfConfig,
};

impl SrIovConfig {
    // * Set 'vfs: []' to None which is just reverting all VF config to default.
    // * Set `vf.iface_name` empty string,
    pub(crate) fn sanitize_desired_for_verify(&mut self) {
        if let Some(vfs) = self.vfs.as_mut() {
            for vf in vfs.iter_mut() {
                vf.iface_name = String::new();
            }
            if vfs.is_empty() {
                self.vfs = None;
            }
        }
    }

    pub(crate) fn update(&mut self, other: Option<&SrIovConfig>) {
        if let Some(other) = other {
            if let Some(autoprobe) = other.drivers_autoprobe {
                self.drivers_autoprobe = Some(autoprobe);
            }
            if let Some(total_vfs) = other.total_vfs {
                self.total_vfs = Some(total_vfs);
            }
            if let Some(vfs) = other.vfs.as_ref() {
                self.vfs = Some(vfs.clone());
            }
        }
    }

    // Many SRIOV card require extra time for kernel and udev to setup the
    // VF interface. This function will wait VF interface been found in
    // cur_ifaces.
    // This function does not handle the decrease of SRIOV count(interface been
    // removed from kernel) as our test showed kernel does not require extra
    // time on deleting interface.
    pub(crate) fn verify_sriov(
        &self,
        pf_name: &str,
        cur_ifaces: &Interfaces,
    ) -> Result<(), NmstateError> {
        let cur_pf_iface =
            match cur_ifaces.get_iface(pf_name, InterfaceType::Ethernet) {
                Some(Interface::Ethernet(i)) => i,
                _ => {
                    return Err(NmstateError::new(
                        ErrorKind::SrIovVfNotFound,
                        format!("Failed to find PF interface {pf_name}"),
                    ));
                }
            };

        if let Some(desired_autoprobe) = self.drivers_autoprobe {
            if !desired_autoprobe {
                return Ok(());
            }
        }

        if let Some(cur_autoprobe) = cur_pf_iface
            .ethernet
            .as_ref()
            .and_then(|eth_conf| eth_conf.sr_iov.as_ref())
            .and_then(|sriov_conf| sriov_conf.drivers_autoprobe.as_ref())
        {
            if !cur_autoprobe {
                return Ok(());
            }
        }

        let vfs = if let Some(vfs) = cur_pf_iface
            .ethernet
            .as_ref()
            .and_then(|eth_conf| eth_conf.sr_iov.as_ref())
            .and_then(|sriov_conf| sriov_conf.vfs.as_ref())
        {
            vfs
        } else {
            return Ok(());
        };
        for vf in vfs {
            if vf.iface_name.is_empty() {
                return Err(NmstateError::new(
                    ErrorKind::SrIovVfNotFound,
                    format!(
                        "Failed to find VF {} interface name of PF {pf_name}",
                        vf.id
                    ),
                ));
            } else if cur_ifaces
                .get_iface(vf.iface_name.as_str(), InterfaceType::Ethernet)
                .is_none()
            {
                return Err(NmstateError::new(
                    ErrorKind::SrIovVfNotFound,
                    format!(
                        "Find VF {} interface name {} of PF {pf_name} \
                        is not exist yet",
                        vf.id, &vf.iface_name
                    ),
                ));
            }
        }
        Ok(())
    }
}

impl Interfaces {
    pub(crate) fn has_sriov_naming(&self) -> bool {
        self.kernel_ifaces
            .values()
            .any(|i| i.name().starts_with(SrIovConfig::VF_NAMING_PREFIX))
    }

    pub(crate) fn use_pseudo_sriov_vf_name(&self, current: &mut Self) {
        let mut new_vf_names: Vec<String> = Vec::new();

        for (des_iface, des_sriov_count) in
            self.kernel_ifaces.values().filter_map(|i| {
                if let Interface::Ethernet(eth_iface) = i {
                    let sriov_count = eth_iface
                        .ethernet
                        .as_ref()
                        .and_then(|e| e.sr_iov.as_ref())
                        .and_then(|s| s.total_vfs)
                        .unwrap_or_default();
                    if sriov_count > 0 {
                        Some((eth_iface, sriov_count))
                    } else {
                        None
                    }
                } else {
                    None
                }
            })
        {
            let cur_iface: &mut Interface = match current
                .kernel_ifaces
                .entry(des_iface.base.name.clone())
            {
                Entry::Occupied(o) => o.into_mut(),
                Entry::Vacant(v) => {
                    v.insert(Interface::Ethernet(des_iface.clone()))
                }
            };

            let des_sriov_conf = if let Some(c) =
                des_iface.ethernet.as_ref().and_then(|e| e.sr_iov.as_ref())
            {
                c
            } else {
                continue;
            };

            let cur_iface = if let Interface::Ethernet(i) = cur_iface {
                i
            } else {
                continue;
            };

            // Only add psudo VF if current SRIOV setting differs
            let cur_sriov_count = cur_iface
                .ethernet
                .as_ref()
                .and_then(|e| e.sr_iov.as_ref())
                .and_then(|s| s.total_vfs)
                .unwrap_or_default();
            if cur_sriov_count < des_sriov_count {
                let cur_vfs = cur_iface
                    .ethernet
                    .get_or_insert(EthernetConfig {
                        sr_iov: Some(des_sriov_conf.clone()),
                        ..Default::default()
                    })
                    .sr_iov
                    .get_or_insert(SrIovConfig::default())
                    .vfs
                    .get_or_insert(Vec::new());
                for vfid in cur_sriov_count..des_sriov_count {
                    let psudo_vf_name =
                        format!("{}v{vfid}", des_iface.base.name);
                    new_vf_names.push(psudo_vf_name.clone());
                    match cur_vfs.get_mut(vfid as usize) {
                        Some(vf) => {
                            vf.id = vfid;
                            if vf.iface_name.is_empty() {
                                vf.iface_name = psudo_vf_name;
                            }
                        }
                        None => {
                            cur_vfs.push(SrIovVfConfig {
                                id: vfid,
                                iface_name: psudo_vf_name,
                                ..Default::default()
                            });
                        }
                    }
                }
            }
        }
        for psudo_vf_name in new_vf_names {
            current.push(Interface::Ethernet(EthernetInterface {
                base: BaseInterface {
                    name: psudo_vf_name,
                    iface_type: InterfaceType::Ethernet,
                    ..Default::default()
                },
                ..Default::default()
            }));
        }
    }
}
