// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;
use std::iter::FromIterator;

use serde::Deserialize;

use crate::{
    ErrorKind, Interface, InterfaceState, InterfaceType, Interfaces,
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
                    log::debug!(
                        "Merging interface {:?} into {:?}",
                        other_iface,
                        self_iface
                    );
                    self_iface.update(other_iface);
                }
                None => {
                    log::debug!("Appending new interface {:?}", other_iface);
                    new_ifaces.push(other_iface);
                }
            }
        }
        for new_iface in new_ifaces {
            self.push(new_iface.clone());
        }
    }

    fn ignored_kernel_iface_names(&self) -> HashSet<String> {
        let mut ret = HashSet::new();
        for iface in self.kernel_ifaces.values().filter(|i| i.is_ignore()) {
            ret.insert(iface.name().to_string());
        }
        ret
    }

    fn ignored_user_iface_name_types(
        &self,
    ) -> HashSet<(String, InterfaceType)> {
        let mut ret = HashSet::new();
        for iface in self.user_ifaces.values().filter(|i| i.is_ignore()) {
            ret.insert((iface.name().to_string(), iface.iface_type()));
        }
        ret
    }

    // Not allowing changing veth peer away from ignored peer unless previous
    // peer changed from ignore to managed
    pub(crate) fn pre_ignore_check(
        &self,
        current: &Self,
        ignored_kernel_iface_names: &[String],
    ) -> Result<(), NmstateError> {
        for iface in self
            .kernel_ifaces
            .values()
            .filter(|i| i.iface_type() == InterfaceType::Veth)
        {
            if let (
                Interface::Ethernet(des_iface),
                Some(Interface::Ethernet(cur_iface)),
            ) = (iface, current.get_iface(iface.name(), InterfaceType::Veth))
            {
                if let (Some(des_peer), Some(cur_peer)) = (
                    des_iface.veth.as_ref().map(|v| v.peer.as_str()),
                    cur_iface.veth.as_ref().map(|v| v.peer.as_str()),
                ) {
                    if des_peer != cur_peer
                        && ignored_kernel_iface_names
                            .contains(&cur_peer.to_string())
                    {
                        let e = NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Veth interface {} is currently holding \
                                peer {} which is marked as ignored. \
                                Hence not allowing changing its peer \
                                to {}. Please remove this veth pair \
                                before changing veth peer",
                                iface.name(),
                                cur_peer,
                                des_peer
                            ),
                        );
                        log::error!("{}", e);
                        return Err(e);
                    }
                }
            }
        }
        Ok(())
    }

    pub(crate) fn verify(
        &self,
        pre_apply_current: &Self,
        cur_ifaces: &Self,
    ) -> Result<(), NmstateError> {
        let mut self_clone = self.clone();
        let (ignored_kernel_ifaces, ignored_user_ifaces) =
            get_ignored_ifaces(self, cur_ifaces);

        self_clone.remove_ignored_ifaces(
            &ignored_kernel_ifaces,
            &ignored_user_ifaces,
        );
        let mut cur_clone = cur_ifaces.clone();
        cur_clone.remove_ignored_ifaces(
            &ignored_kernel_ifaces,
            &ignored_user_ifaces,
        );
        cur_clone.remove_unknown_type_port();
        self_clone.resolve_sriov_reference(pre_apply_current)?;

        for iface in self_clone.to_vec() {
            if iface.is_absent() || (iface.is_virtual() && iface.is_down()) {
                if let Some(cur_iface) =
                    cur_clone.get_iface(iface.name(), iface.iface_type())
                {
                    verify_desire_absent_but_found_in_current(
                        iface, cur_iface,
                    )?;
                }
            } else if let Some(cur_iface) =
                cur_clone.get_iface(iface.name(), iface.iface_type())
            {
                let pre_apply_cur_iface = pre_apply_current
                    .get_iface(iface.name(), iface.iface_type());
                // Do not verify physical interface with state:down
                if !iface.is_down() {
                    iface.verify(pre_apply_cur_iface, cur_iface)?;
                    if let Interface::Ethernet(eth_iface) = iface {
                        if eth_iface.sriov_is_enabled() {
                            eth_iface.verify_sriov(cur_ifaces)?;
                        }
                    }
                }
            } else {
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

    pub(crate) fn remove_ignored_ifaces(
        &mut self,
        kernel_iface_names: &[String],
        user_ifaces: &[(String, InterfaceType)],
    ) {
        self.kernel_ifaces
            .retain(|iface_name, _| !kernel_iface_names.contains(iface_name));

        self.user_ifaces.retain(|(iface_name, iface_type), _| {
            !user_ifaces.contains(&(iface_name.to_string(), iface_type.clone()))
        });

        let kernel_iface_names = HashSet::from_iter(
            kernel_iface_names.iter().map(|i| i.to_string()),
        );

        for iface in self
            .kernel_ifaces
            .values_mut()
            .chain(self.user_ifaces.values_mut())
        {
            if let Some(ports) = iface.ports() {
                let ports: HashSet<String> =
                    HashSet::from_iter(ports.iter().map(|p| p.to_string()));
                for ignore_port in kernel_iface_names.intersection(&ports) {
                    iface.remove_port(ignore_port);
                }
            }
            if iface.iface_type() == InterfaceType::Veth {
                if let Interface::Ethernet(eth_iface) = iface {
                    if let Some(veth_conf) = eth_iface.veth.as_ref() {
                        if kernel_iface_names.contains(veth_conf.peer.as_str())
                        {
                            log::info!(
                                "Veth interface {} is holding ignored peer {}",
                                eth_iface.base.name,
                                veth_conf.peer.as_str()
                            );
                            eth_iface.veth = None;
                            eth_iface.base.iface_type = InterfaceType::Ethernet;
                        }
                    }
                }
            }
        }
    }

    pub(crate) fn get_iface_mut<'a, 'b>(
        &'a mut self,
        iface_name: &'b str,
        iface_type: InterfaceType,
    ) -> Option<&'a mut Interface> {
        if iface_type.is_userspace() {
            self.user_ifaces
                .get_mut(&(iface_name.to_string(), iface_type))
        } else {
            self.kernel_ifaces.get_mut(&iface_name.to_string())
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

    pub(crate) fn resolve_unknown_ifaces(
        &mut self,
        cur_ifaces: &Self,
    ) -> Result<(), NmstateError> {
        let mut resolved_ifaces: Vec<Interface> = Vec::new();
        for (iface_name, iface) in self.kernel_ifaces.iter() {
            if iface.iface_type() != InterfaceType::Unknown || iface.is_ignore()
            {
                continue;
            }
            if iface.is_absent() {
                for cur_iface in cur_ifaces.to_vec() {
                    if cur_iface.name() == iface_name {
                        let mut new_iface = cur_iface.clone();
                        new_iface.base_iface_mut().state =
                            InterfaceState::Absent;
                        resolved_ifaces.push(new_iface);
                    }
                }
            } else {
                let mut founds = Vec::new();
                for cur_iface in cur_ifaces.to_vec() {
                    if cur_iface.name() == iface_name {
                        let mut new_iface_value = serde_json::to_value(iface)?;
                        if let Some(obj) = new_iface_value.as_object_mut() {
                            obj.insert(
                                "type".to_string(),
                                serde_json::Value::String(
                                    cur_iface.iface_type().to_string(),
                                ),
                            );
                        }
                        founds.push(new_iface_value);
                    }
                }
                match founds.len() {
                    0 => {
                        let e = NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Failed to find unknown type interface {} \
                                in current state",
                                iface_name
                            ),
                        );
                        log::error!("{}", e);
                        return Err(e);
                    }
                    1 => {
                        let new_iface = Interface::deserialize(&founds[0])?;
                        resolved_ifaces.push(new_iface);
                    }
                    _ => {
                        let e = NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Found 2+ interface matching desired unknown \
                            type interface {}: {:?}",
                                iface_name, &founds
                            ),
                        );
                        log::error!("{}", e);
                        return Err(e);
                    }
                }
            }
        }

        for new_iface in resolved_ifaces {
            self.kernel_ifaces.remove(new_iface.name());
            self.push(new_iface);
        }
        Ok(())
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

// Special cases:
//  * Inherit the ignore state from current if desire not mentioned in interface
//    section
pub(crate) fn get_ignored_ifaces(
    desired: &Interfaces,
    current: &Interfaces,
) -> (Vec<String>, Vec<(String, InterfaceType)>) {
    let mut ignored_kernel_ifaces = desired.ignored_kernel_iface_names();
    let mut ignored_user_ifaces = desired.ignored_user_iface_name_types();
    let desired_kernel_ifaces: HashSet<String> = desired
        .kernel_ifaces
        .values()
        .filter(|i| !i.is_ignore())
        .map(|i| i.name().to_string())
        .collect();
    let desired_user_ifaces: HashSet<(String, InterfaceType)> = desired
        .user_ifaces
        .values()
        .filter(|i| !i.is_ignore())
        .map(|i| (i.name().to_string(), i.iface_type()))
        .collect();

    for iface_name in current.ignored_kernel_iface_names().drain() {
        if !desired_kernel_ifaces.contains(&iface_name) {
            ignored_kernel_ifaces.insert(iface_name);
        }
    }
    for (iface_name, iface_type) in
        current.ignored_user_iface_name_types().drain()
    {
        if !desired_user_ifaces
            .contains(&(iface_name.clone(), iface_type.clone()))
        {
            ignored_user_ifaces.insert((iface_name, iface_type));
        }
    }

    let k_ifaces: Vec<String> = ignored_kernel_ifaces.drain().collect();
    let u_ifaces: Vec<(String, InterfaceType)> =
        ignored_user_ifaces.drain().collect();
    (k_ifaces, u_ifaces)
}
