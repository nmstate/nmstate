// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, Interface, InterfaceType, Interfaces, NmstateError, SrIovConfig,
};

const SRIOV_VF_NAMING_SEPERATOR: char = ':';
const SRIOV_VF_NAMING_PREFIX: &str = "sriov:";

impl SrIovConfig {
    pub(crate) fn update(&mut self, other: Option<&SrIovConfig>) {
        if let Some(other) = other {
            if let Some(total_vfs) = other.total_vfs {
                self.total_vfs = Some(total_vfs);
            }
            if let Some(vfs) = other.vfs.as_ref() {
                self.vfs = Some(vfs.clone());
            }
        }
    }

    // Convert VF MAC address to upper case
    // Ignore 'vfs: []' which is just reverting all VF config to default.
    pub(crate) fn pre_verify_cleanup(&mut self) {
        if let Some(vfs) = self.vfs.as_mut() {
            for vf in vfs.iter_mut() {
                if let Some(address) = vf.mac_address.as_mut() {
                    address.make_ascii_uppercase()
                }
            }
            if vfs.is_empty() {
                self.vfs = None;
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
                    let e = NmstateError::new(
                        ErrorKind::VerificationError,
                        format!("Failed to find PF interface {pf_name}"),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            };

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
            if vf.iface_name.as_str().is_empty() {
                let e = NmstateError::new(
                    ErrorKind::VerificationError,
                    format!(
                        "Failed to find VF {} interface name of PF {pf_name}",
                        vf.id
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            } else if cur_ifaces
                .get_iface(vf.iface_name.as_str(), InterfaceType::Ethernet)
                .is_none()
            {
                let e = NmstateError::new(
                    ErrorKind::VerificationError,
                    format!(
                        "Find VF {} interface name {} of PF {pf_name} \
                        is not exist yet",
                        vf.id, &vf.iface_name
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
        Ok(())
    }
}

impl Interfaces {
    pub(crate) fn resolve_sriov_reference(
        &mut self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        self.resolve_sriov_reference_iface_name(current)?;
        self.resolve_sriov_reference_port_name(current)?;
        Ok(())
    }

    fn resolve_sriov_reference_iface_name(
        &mut self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        let mut changed_iface_names: Vec<String> = Vec::new();
        for iface in self
            .kernel_ifaces
            .values_mut()
            .filter(|i| i.iface_type() == InterfaceType::Ethernet)
        {
            if let Some((pf_name, vf_id)) = parse_sriov_vf_naming(iface.name())?
            {
                if let Some(vf_iface_name) =
                    get_sriov_vf_iface_name(current, pf_name, vf_id)
                {
                    changed_iface_names.push(iface.name().to_string());
                    log::info!(
                        "SR-IOV VF {} resolved to interface name {}",
                        iface.name(),
                        vf_iface_name
                    );
                    iface.base_iface_mut().name = vf_iface_name;
                } else {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Failed to find SR-IOV VF interface name for {}",
                            iface.name()
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
        }
        for changed_iface_name in changed_iface_names {
            if let Some(iface) = self.kernel_ifaces.remove(&changed_iface_name)
            {
                if self.kernel_ifaces.get(iface.name()).is_some() {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "SR-IOV VF name {} has been resolved as interface \
                            {}, but it is already defined in desire state",
                            changed_iface_name,
                            iface.name()
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
                self.kernel_ifaces.insert(iface.name().to_string(), iface);
            }
        }
        Ok(())
    }

    fn resolve_sriov_reference_port_name(
        &mut self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        //  pending_changes:
        //      Vec<(ctrl_name, ctrl_iface_type, origin_name, new_name)>
        let mut pending_changes = Vec::new();
        for iface in self
            .kernel_ifaces
            .values()
            .chain(self.user_ifaces.values())
            .filter(|i| i.is_controller())
        {
            let ports = match iface.ports() {
                Some(p) => p,
                None => continue,
            };
            for port in ports {
                if let Some((pf_name, vf_id)) = parse_sriov_vf_naming(port)? {
                    if let Some(vf_iface_name) =
                        get_sriov_vf_iface_name(current, pf_name, vf_id)
                    {
                        log::info!(
                            "SR-IOV VF {} resolved to interface name {}",
                            port,
                            vf_iface_name
                        );
                        pending_changes.push((
                            iface.name().to_string(),
                            iface.iface_type(),
                            port.to_string(),
                            vf_iface_name.to_string(),
                        ));
                    }
                }
            }
        }
        for (ctrl, ctrl_iface_type, origin_name, new_name) in pending_changes {
            if let Some(iface) = self.get_iface_mut(&ctrl, ctrl_iface_type) {
                iface.change_port_name(origin_name.as_str(), new_name);
            }
        }
        Ok(())
    }
}

fn parse_sriov_vf_naming(
    iface_name: &str,
) -> Result<Option<(&str, u32)>, NmstateError> {
    if iface_name.starts_with(SRIOV_VF_NAMING_PREFIX) {
        let names: Vec<&str> =
            iface_name.split(SRIOV_VF_NAMING_SEPERATOR).collect();
        if names.len() == 3 {
            match names[2].parse::<u32>() {
                Ok(vf_id) => Ok(Some((names[1], vf_id))),
                Err(e) => {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Invalid SR-IOV VF ID in {}, correct format \
                            is 'sriov:<pf_name>:<vf_id>', error: {}",
                            iface_name, e
                        ),
                    );
                    log::error!("{}", e);
                    Err(e)
                }
            }
        } else {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Invalid SR-IOV VF name {}, correct format is \
                    'sriov:<pf_name>:<vf_id>'",
                    iface_name,
                ),
            );
            log::error!("{}", e);
            Err(e)
        }
    } else {
        Ok(None)
    }
}

pub(crate) fn get_sriov_vf_iface_name(
    current: &Interfaces,
    pf_name: &str,
    vf_id: u32,
) -> Option<String> {
    if let Some(Interface::Ethernet(pf_iface)) =
        current.get_iface(pf_name, InterfaceType::Ethernet)
    {
        if let Some(vfs) = pf_iface
            .ethernet
            .as_ref()
            .and_then(|e| e.sr_iov.as_ref())
            .and_then(|s| s.vfs.as_ref())
        {
            for vf in vfs {
                if vf.id == vf_id {
                    if !vf.iface_name.is_empty() {
                        return Some(vf.iface_name.clone());
                    }
                    break;
                }
            }
        }
    }
    None
}
