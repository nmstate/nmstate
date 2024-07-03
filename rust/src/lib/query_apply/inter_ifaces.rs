// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{
    state::{gen_diff_json_value, merge_json_value},
    ErrorKind, Interface, InterfaceIdentifier, InterfaceType, Interfaces,
    MergedInterfaces, NmstateError,
};

impl Interfaces {
    pub(crate) fn has_up_ovs_iface(&self) -> bool {
        self.iter().any(|i| {
            i.iface_type() == InterfaceType::OvsBridge
                || i.iface_type() == InterfaceType::OvsInterface
        })
    }

    pub fn update(&mut self, other: &Self) {
        let mut new_ifaces: Vec<Interface> = Vec::new();
        let other_ifaces = other.to_vec();
        for other_iface in other_ifaces {
            let self_iface = if other_iface.is_userspace() {
                self.get_iface_mut(other_iface.name(), other_iface.iface_type())
            } else {
                self.kernel_ifaces.get_mut(other_iface.name())
            };
            match self_iface {
                Some(self_iface) => {
                    // The OVS with netdev datapath will use `TUN` interface
                    // as kernel representative
                    if self_iface.iface_type() == InterfaceType::Tun
                        && other_iface.iface_type()
                            == InterfaceType::OvsInterface
                    {
                        if let Interface::OvsInterface(other_ovs_iface) =
                            other_iface
                        {
                            let mut new_iface = other_ovs_iface.clone();
                            new_iface.base = self_iface.base_iface().clone();
                            new_iface.base.state = other_ovs_iface.base.state;
                            new_iface.base.iface_type =
                                InterfaceType::OvsInterface;
                            new_iface
                                .base
                                .controller
                                .clone_from(&other_ovs_iface.base.controller);
                            new_iface.base.controller_type.clone_from(
                                &other_ovs_iface.base.controller_type,
                            );
                            let mut new_iface =
                                Interface::OvsInterface(new_iface);
                            new_iface.update(other_iface);
                            new_ifaces.push(new_iface);
                        }
                    } else {
                        self_iface.update(other_iface);
                    }
                }
                None => {
                    new_ifaces.push(other_iface.clone());
                }
            }
        }
        for new_iface in new_ifaces {
            self.push(new_iface);
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

    pub(crate) fn tidy_up_for_retreive(&mut self) {
        // Purge user space ignored interfaces
        self.user_ifaces.retain(|_, iface| !iface.is_ignore());

        // Include mac address, interface type of subordinates in controller's
        // configure
        self.include_mac_and_type_in_controller_and_parent();
    }

    fn include_mac_and_type_in_controller_and_parent(&mut self) {
        let mut port_name_to_mac_type: HashMap<
            String,
            (String, InterfaceType),
        > = HashMap::new();

        for iface in self
            .kernel_ifaces
            .values()
            .filter(|i| i.controller().is_some())
        {
            if let Some(mac) =
                iface.base_iface().permanent_mac_address.as_deref()
            {
                port_name_to_mac_type.insert(
                    iface.name().to_string(),
                    (mac.to_string(), iface.iface_type()),
                );
            }
        }

        for iface in self
            .kernel_ifaces
            .values_mut()
            .chain(self.user_ifaces.values_mut())
            .filter(|i| i.is_controller())
        {
            for port_name in iface.ports().unwrap_or_default() {
                if let (mac, iface_type) = port_name_to_mac_type.get(port_name)
                {
                    iface.set_port_mac_and_type(port, mac, iface_type);
                }
            }
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
    pub(crate) fn gen_diff(&self) -> Result<Interfaces, NmstateError> {
        let mut ret = Interfaces::default();
        for merged_iface in self
            .kernel_ifaces
            .values()
            .chain(self.user_ifaces.values())
            .filter(|i| i.is_desired() && i.desired != i.current)
        {
            let des_iface = if let Some(i) = merged_iface.for_apply.as_ref() {
                i
            } else {
                continue;
            };
            let cur_iface = if let Some(i) = merged_iface.current.as_ref() {
                let mut cur_iface = i.clone();
                cur_iface.sanitize(false).ok();
                cur_iface
            } else {
                ret.push(des_iface.clone());
                continue;
            };
            let desired_value = serde_json::to_value(des_iface)?;
            let current_value = serde_json::to_value(&cur_iface)?;
            if let Some(diff_value) =
                gen_diff_json_value(&desired_value, &current_value)
            {
                let mut new_iface = des_iface.clone_name_type_only();
                new_iface.base_iface_mut().state = des_iface.base_iface().state;
                let mut new_iface_value = serde_json::to_value(&new_iface)?;
                merge_json_value(&mut new_iface_value, &diff_value);
                let new_iface =
                    serde_json::from_value::<Interface>(new_iface_value)?;
                ret.push(new_iface);
            }
        }
        Ok(ret)
    }

    pub(crate) fn verify(
        &self,
        current: &Interfaces,
    ) -> Result<(), NmstateError> {
        let mut merged = self.clone();
        let mut current = current.clone();
        current.remove_ignored_ifaces(self.ignored_ifaces.as_slice());
        current.remove_unknown_type_port();
        merged.process_allow_extra_ovs_patch_ports_for_verify(&mut current);

        for iface in current
            .kernel_ifaces
            .values_mut()
            .chain(current.user_ifaces.values_mut())
        {
            iface.sanitize(false).ok();
            iface.sanitize_current_for_verify();
        }

        for des_iface in merged.iter_mut().filter(|i| i.is_desired()) {
            let iface = if let Some(i) = des_iface.for_verify.as_mut() {
                i
            } else {
                continue;
            };
            iface.sanitize(false).ok();
            iface.sanitize_desired_for_verify();
        }

        for des_iface in merged.iter_mut().filter(|i| i.is_desired()) {
            let iface = if let Some(i) = des_iface.for_verify.as_mut() {
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
