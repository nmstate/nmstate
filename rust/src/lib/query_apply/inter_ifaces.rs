// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, Interface, InterfaceType, Interfaces, MergedInterfaces,
    NmstateError,
};

impl Interfaces {
    pub fn update(&mut self, other: &Self) {
        let mut new_ifaces: Vec<&Interface> = Vec::new();
        let other_ifaces = other.to_vec();
        for other_iface in &other_ifaces {
            match self
                .get_iface_mut(other_iface.name(), other_iface.iface_type())
            {
                Some(self_iface) => {
                    self_iface.update(other_iface);
                }
                None => {
                    new_ifaces.push(other_iface);
                }
            }
        }
        for new_iface in new_ifaces {
            self.push(new_iface.clone());
        }
    }

    fn remove_unknown_type_port(&mut self) {
        let mut pending_actions: Vec<(String, InterfaceType, String)> =
            Vec::new();
        for iface in
            self.kernel_ifaces.values().chain(self.user_ifaces.values())
        {
            if !iface.is_controller() {
                continue;
            }
            for port_name in find_unknown_type_port(iface, self) {
                pending_actions.push((
                    iface.name().to_string(),
                    iface.iface_type(),
                    port_name.to_string(),
                ));
            }
        }

        for (ctrl_name, ctrl_type, port_name) in pending_actions {
            if ctrl_type.is_userspace() {
                if let Some(iface) =
                    self.user_ifaces.get_mut(&(ctrl_name, ctrl_type))
                {
                    iface.remove_port(&port_name)
                }
            } else if let Some(iface) = self.kernel_ifaces.get_mut(&ctrl_name) {
                iface.remove_port(&port_name)
            }
        }
    }

    pub(crate) fn has_sriov_enabled(&self) -> bool {
        self.kernel_ifaces.values().any(|i| {
            if let Interface::Ethernet(eth_iface) = i {
                eth_iface.sriov_is_enabled()
            } else {
                false
            }
        })
    }

    pub(crate) fn hide_controller_prop(&mut self) {
        for iface in self.kernel_ifaces.values_mut() {
            iface.base_iface_mut().controller = None;
        }
    }
}

fn find_unknown_type_port<'a>(
    iface: &'a Interface,
    cur_ifaces: &Interfaces,
) -> Vec<&'a str> {
    let mut ret: Vec<&str> = Vec::new();
    if let Some(port_names) = iface.ports() {
        for port_name in port_names {
            if let Some(port_iface) =
                cur_ifaces.get_iface(port_name, InterfaceType::Unknown)
            {
                if port_iface.iface_type() == InterfaceType::Unknown {
                    ret.push(port_name);
                }
            } else {
                // Remove not found interface also
                ret.push(port_name);
            }
        }
    }
    ret
}

fn verify_desire_absent_but_found_in_current(
    des_iface: &Interface,
    cur_iface: &Interface,
) -> Result<(), NmstateError> {
    if cur_iface.is_virtual() {
        // Virtual interface should be deleted by absent action
        let e = NmstateError::new(
            ErrorKind::VerificationError,
            format!(
                "Absent/Down interface {}/{} still found as {:?}",
                des_iface.name(),
                des_iface.iface_type(),
                cur_iface
            ),
        );
        log::error!("{}", e);
        Err(e)
    } else {
        // Hard to predict real hardware state due to backend variety.
        Ok(())
    }
}

impl MergedInterfaces {
    pub(crate) fn state_for_apply(&self) -> Interfaces {
        let mut ifaces = Interfaces::new();
        for merged_iface in self
            .kernel_ifaces
            .values()
            .chain(self.user_ifaces.values())
            .filter(|i| i.is_changed())
        {
            if let Some(iface) = merged_iface.for_apply.as_ref() {
                ifaces.push(iface.clone());
            }
        }
        ifaces
    }

    pub(crate) fn verify(
        &self,
        current: &Interfaces,
    ) -> Result<(), NmstateError> {
        let mut current = current.clone();
        current.remove_ignored_ifaces(self.ignored_ifaces.as_slice());
        current.remove_unknown_type_port();
        for iface in current
            .kernel_ifaces
            .values_mut()
            .chain(current.user_ifaces.values_mut())
        {
            iface.sanitize().ok();
            iface.sanitize_for_verify();
        }

        for des_iface in self.iter().filter(|i| i.is_desired()) {
            let iface = if let Some(i) = des_iface.for_verify.as_ref() {
                i
            } else {
                continue;
            };
            if iface.is_absent() || (iface.is_virtual() && iface.is_down()) {
                if let Some(cur_iface) =
                    current.get_iface(iface.name(), iface.iface_type())
                {
                    verify_desire_absent_but_found_in_current(
                        iface, cur_iface,
                    )?;
                }
            } else if let Some(cur_iface) =
                current.get_iface(iface.name(), iface.iface_type())
            {
                // Do not verify physical interface with state:down
                if iface.is_up() {
                    iface.verify(cur_iface)?;
                    if let Interface::Ethernet(eth_iface) = iface {
                        if eth_iface.sriov_is_enabled() {
                            eth_iface.verify_sriov(&current)?;
                        }
                    }
                }
            } else if iface.is_up() {
                return Err(NmstateError::new(
                    ErrorKind::VerificationError,
                    format!(
                        "Failed to find desired interface {} {:?}",
                        iface.name(),
                        iface.iface_type()
                    ),
                ));
            }
        }
        Ok(())
    }
}
