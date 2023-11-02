// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, Interface, InterfaceType, Interfaces, NmstateError, SrIovConfig,
};

impl SrIovConfig {
    // * Set 'vfs: []' to None which is just reverting all VF config to default.
    pub(crate) fn sanitize_desired_for_verify(&mut self) {
        if let Some(vfs) = self.vfs.as_mut() {
            if vfs.is_empty() {
                self.vfs = None;
            }
        }
    }

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
