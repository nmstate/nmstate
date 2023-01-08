// SPDX-License-Identifier: Apache-2.0

use std::collections::{HashMap, HashSet};
use std::iter::FromIterator;

use crate::{
    BondMode, ErrorKind, Interface, InterfaceState, InterfaceType, Interfaces,
    MergedInterface, MergedInterfaces, NmstateError, OvsInterface,
};

fn is_port_overbook(
    port_to_ctrl: &mut HashMap<String, String>,
    port: &str,
    ctrl: &str,
) -> Result<(), NmstateError> {
    if let Some(cur_ctrl) = port_to_ctrl.get(port) {
        let e = NmstateError::new(
            ErrorKind::InvalidArgument,
            format!(
                "Port {port} is overbooked by two controller: {ctrl}, {cur_ctrl}"
            ),
        );
        log::error!("{}", e);
        return Err(e);
    } else {
        port_to_ctrl.insert(port.to_string(), ctrl.to_string());
    }
    Ok(())
}

impl MergedInterfaces {
    // Check whether user defined both controller property and port list of
    // controller interface, examples of invalid desire state:
    //  * eth1 has controller: br1, but br1 has no eth1 in port list
    //  * eth2 has controller: br1, but br2 has eth2 in port list
    //  * eth1 has controller: Some("") (detach), but br1 has eth1 in port list
    pub(crate) fn validate_controller_and_port_list_confliction(
        &self,
    ) -> Result<(), NmstateError> {
        self.validate_controller_not_in_port_list()?;
        self.validate_controller_in_other_port_list()?;
        Ok(())
    }

    fn validate_controller_not_in_port_list(&self) -> Result<(), NmstateError> {
        for merged_iface in self.kernel_ifaces.values() {
            if merged_iface.desired.is_none() || !merged_iface.merged.is_up() {
                continue;
            }

            if let Some(des_ctrl_name) = merged_iface
                .desired
                .as_ref()
                .and_then(|i| i.base_iface().controller.as_ref())
            {
                // Detaching from current controller
                if des_ctrl_name.is_empty() {
                    continue;
                }

                if let Some(ctrl_iface) = self
                    .user_ifaces
                    .get(&(des_ctrl_name.to_string(), InterfaceType::OvsBridge))
                    .or_else(|| self.kernel_ifaces.get(des_ctrl_name))
                {
                    // controller iface not mentioned in desire state
                    if !ctrl_iface.is_desired() {
                        continue;
                    }
                    if let Some(ports) = ctrl_iface.merged.ports() {
                        if !ports.contains(&des_ctrl_name.as_str()) {
                            return Err(NmstateError::new(
                                ErrorKind::InvalidArgument,
                                format!(
                                    "Interface {} has controller {} \
                                    but not listed in port list of \
                                    controller interface",
                                    merged_iface.merged.name(),
                                    des_ctrl_name,
                                ),
                            ));
                        }
                    }
                } else {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Interface {} desired controller \
                            {des_ctrl_name} not found",
                            merged_iface.merged.name()
                        ),
                    ));
                }
            }
        }
        Ok(())
    }

    fn validate_controller_in_other_port_list(
        &self,
    ) -> Result<(), NmstateError> {
        let mut port_to_ctrl = HashMap::new();
        for iface in self.iter().filter(|i| i.is_desired() && i.merged.is_up())
        {
            if let Some(port_names) = iface.merged.ports() {
                for port_name in port_names {
                    port_to_ctrl.insert(port_name, iface.merged.name());
                }
            }
        }
        for iface in self
            .kernel_ifaces
            .values()
            .filter(|i| i.is_desired() && i.merged.is_up())
        {
            let des_ctrl_name = if let Some(n) = iface
                .desired
                .as_ref()
                .and_then(|i| i.base_iface().controller.as_ref())
            {
                n
            } else {
                continue;
            };
            if let Some(ctrl_name) = port_to_ctrl.get(iface.merged.name()) {
                if des_ctrl_name != ctrl_name {
                    if des_ctrl_name.is_empty() {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Interface {} desired to detach controller \
                                via controller property set to '', but \
                                still been listed as port of controller {} ",
                                iface.merged.name(),
                                ctrl_name
                            ),
                        ));
                    } else {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Interface {} has controller property set \
                                to {}, but been listed as port of \
                                controller {} ",
                                iface.merged.name(),
                                des_ctrl_name,
                                ctrl_name
                            ),
                        ));
                    }
                }
            }
        }
        Ok(())
    }

    pub(crate) fn handle_changed_ports(&mut self) -> Result<(), NmstateError> {
        let mut pending_changes: HashMap<
            String,
            (String, Option<InterfaceType>),
        > = HashMap::new();
        for iface in self.iter() {
            if !iface.is_desired() || !iface.merged.is_controller() {
                continue;
            }
            if let Some((attached_ports, detached_ports)) =
                iface.get_changed_ports()
            {
                for port_name in attached_ports {
                    pending_changes.insert(
                        port_name.to_string(),
                        (
                            iface.merged.name().to_string(),
                            Some(iface.merged.iface_type()),
                        ),
                    );
                }
                for port_name in detached_ports {
                    // Port might move from one controller to another, if there
                    // is already a pending action for this
                    // port, we don't override it.
                    pending_changes
                        .entry(port_name.to_string())
                        .or_insert_with(|| (String::new(), None));
                }
            }
        }

        for (iface_name, (ctrl_name, ctrl_type)) in pending_changes.drain() {
            if let Some(iface) = self.kernel_ifaces.get_mut(&iface_name) {
                if !iface.is_changed() {
                    self.insert_order.push((
                        iface.merged.name().to_string(),
                        iface.merged.iface_type(),
                    ));
                }
                iface.apply_ctrller_change(ctrl_name, ctrl_type)?;
            } else {
                // OVS internal interface could be created by its controller OVS
                // Bridge
                if ctrl_type == Some(InterfaceType::OvsBridge) {
                    log::info!(
                        "Creating new OVS internal interface {iface_name} to \
                        edit as its controller {ctrl_name} required so",
                    );
                    self.kernel_ifaces.insert(
                        iface_name.to_string(),
                        MergedInterface::new(
                            Some(Interface::OvsInterface(
                                OvsInterface::new_with_name_and_ctrl(
                                    &iface_name,
                                    &ctrl_name,
                                ),
                            )),
                            None,
                        )?,
                    );
                    self.insert_order.push((
                        iface_name.to_string(),
                        InterfaceType::OvsInterface,
                    ));
                } else if !ctrl_name.is_empty() {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Controller interface {ctrl_name} is \
                                holding unknown port {iface_name}"
                        ),
                    ));
                }
            }
        }

        Ok(())
    }

    // When only port iface with `controller` peppery without its controller
    // interface been mentioned in desired state, we need to resolve its
    // controller type for backend to proceed.
    pub(crate) fn resolve_port_iface_controller_type(
        &mut self,
    ) -> Result<(), NmstateError> {
        let mut pending_changes: HashMap<String, (String, InterfaceType)> =
            HashMap::new();
        // Port interface can only kernel interface
        for iface in self
            .kernel_ifaces
            .values()
            .filter(|i| i.is_desired() && i.merged.is_up())
        {
            if let (Some(ctrl_name), None) = (
                iface
                    .desired
                    .as_ref()
                    .and_then(|i| i.base_iface().controller.as_ref()),
                iface
                    .desired
                    .as_ref()
                    .and_then(|i| i.base_iface().controller_type.as_ref()),
            ) {
                if ctrl_name.is_empty() {
                    continue;
                }

                match self
                    .user_ifaces
                    .get(&(ctrl_name.to_string(), InterfaceType::OvsBridge))
                    .or_else(|| self.kernel_ifaces.get(ctrl_name))
                {
                    Some(ctrl_iface) => {
                        log::debug!(
                            "Setting controller type of interface {} to {}",
                            iface.merged.name(),
                            ctrl_iface.merged.name(),
                        );
                        pending_changes.insert(
                            iface.merged.name().to_string(),
                            (
                                ctrl_name.to_string(),
                                ctrl_iface.merged.iface_type(),
                            ),
                        );
                    }
                    None => {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "The controller {} of interface {} \
                                does not exists",
                                ctrl_name,
                                iface.merged.name()
                            ),
                        ));
                    }
                }
            }
        }
        for (iface_name, (ctrl_name, ctrl_type)) in pending_changes.drain() {
            if let Some(iface) = self.kernel_ifaces.get_mut(&iface_name) {
                iface.apply_ctrller_change(ctrl_name, Some(ctrl_type))?;
            }
        }
        Ok(())
    }

    // Return True if we have all up_priority fixed.
    pub(crate) fn set_ifaces_up_priority(&mut self) -> bool {
        // Return true when all interface has correct priority.
        let mut ret = true;
        let mut pending_changes: HashMap<String, u32> = HashMap::new();
        // Use the push order to allow user providing help on dependency order

        for (iface_name, iface_type) in &self.insert_order {
            let iface = match self.get_iface(iface_name, iface_type.clone()) {
                Some(i) => {
                    if let Some(i) = i.for_apply.as_ref() {
                        i
                    } else {
                        continue;
                    }
                }
                None => continue,
            };
            if !iface.is_up() {
                continue;
            }

            if iface.base_iface().is_up_priority_valid() {
                continue;
            }

            if let Some(ref ctrl_name) = iface.base_iface().controller {
                if ctrl_name.is_empty() {
                    continue;
                }
                let ctrl_iface = self
                    .get_iface(
                        ctrl_name,
                        iface
                            .base_iface()
                            .controller_type
                            .clone()
                            .unwrap_or_default(),
                    )
                    .and_then(|i| i.for_apply.as_ref());
                if let Some(ctrl_iface) = ctrl_iface {
                    if let Some(ctrl_pri) = pending_changes.remove(ctrl_name) {
                        pending_changes.insert(ctrl_name.to_string(), ctrl_pri);
                        pending_changes
                            .insert(iface_name.to_string(), ctrl_pri + 1);
                    } else if ctrl_iface.base_iface().is_up_priority_valid() {
                        pending_changes.insert(
                            iface_name.to_string(),
                            ctrl_iface.base_iface().up_priority + 1,
                        );
                    } else {
                        // Its controller does not have valid up priority yet.
                        log::debug!(
                            "Controller {ctrl_name} of {iface_name} is has no \
                            up priority"
                        );
                        ret = false;
                    }
                } else {
                    // Interface has no controller defined in desire
                    continue;
                }
            } else {
                continue;
            }
        }

        // If not remaining unknown up_priority, we set up the parent/child
        // up_priority
        if ret {
            for (iface_name, iface_type) in &self.insert_order {
                let iface = match self.get_iface(iface_name, iface_type.clone())
                {
                    Some(i) => {
                        if let Some(i) = i.for_apply.as_ref() {
                            i
                        } else {
                            continue;
                        }
                    }
                    None => continue,
                };
                if !iface.is_up() {
                    continue;
                }
                if let Some(parent) = iface.parent() {
                    let parent_priority = pending_changes.get(parent).cloned();
                    if let Some(parent_priority) = parent_priority {
                        pending_changes.insert(
                            iface_name.to_string(),
                            parent_priority + 1,
                        );
                    } else if let Some(parent_iface) = self
                        .kernel_ifaces
                        .get(parent)
                        .and_then(|i| i.for_apply.as_ref())
                    {
                        if parent_iface.base_iface().is_up_priority_valid() {
                            pending_changes.insert(
                                iface_name.to_string(),
                                parent_iface.base_iface().up_priority + 1,
                            );
                        }
                    }
                }
            }
        }

        log::debug!("Pending kernel up priority changes {:?}", pending_changes);
        for (iface_name, priority) in pending_changes.iter() {
            if let Some(iface) = self
                .kernel_ifaces
                .get_mut(iface_name)
                .and_then(|i| i.for_apply.as_mut())
            {
                iface.base_iface_mut().up_priority = *priority;
            }
        }

        ret
    }

    pub(crate) fn check_overbook_ports(&self) -> Result<(), NmstateError> {
        let mut port_to_ctrl: HashMap<String, String> = HashMap::new();
        for iface in self.iter().filter(|i| {
            i.merged.is_controller() && i.merged.is_up() && i.is_desired()
        }) {
            let ports = if let Some(p) = iface.merged.ports() {
                p
            } else {
                continue;
            };

            for port in ports {
                is_port_overbook(&mut port_to_ctrl, port, iface.merged.name())?;
            }
        }

        Ok(())
    }

    // Infiniband over IP can only be port of active_backup bond as it is a
    // layer 3 interface like tun.
    pub(crate) fn check_infiniband_as_ports(&self) -> Result<(), NmstateError> {
        let ib_iface_names: HashSet<&str> = self
            .kernel_ifaces
            .values()
            .filter(|iface| {
                iface.merged.iface_type() == InterfaceType::InfiniBand
            })
            .map(|iface| iface.merged.name())
            .collect();

        for iface in self
            .kernel_ifaces
            .values()
            .filter(|i| i.is_desired() && i.merged.is_controller())
            .map(|i| &i.merged)
        {
            if let Some(ports) = iface.ports() {
                let ports = HashSet::from_iter(ports.iter().cloned());
                if !ib_iface_names.is_disjoint(&ports) {
                    if let Interface::Bond(iface) = iface {
                        if iface.mode() == Some(BondMode::ActiveBackup) {
                            continue;
                        }
                    }
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "InfiniBand interface {:?} cannot use as \
                            port of {}. Only active-backup bond allowed.",
                            ib_iface_names.intersection(&ports),
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

impl Interfaces {
    // Automatically convert ignored interface to `state: up` when all below
    // conditions met:
    //  1. Not mentioned in desire state.
    //  2. Been listed as port of a controller.
    //  3. Controller interface is new or does not contains ignored interfaces.
    pub(crate) fn auto_managed_controller_ports(&mut self, current: &Self) {
        // Contains ignored kernel ifaces which is not mentioned in desire
        // states
        let mut not_desired_ignores: HashSet<&str> = HashSet::new();
        let mut full_ignores: HashSet<&str> = HashSet::new();
        for iface in current.kernel_ifaces.values().filter(|i| i.is_ignore()) {
            match self.kernel_ifaces.get(iface.name()) {
                Some(des_iface) => {
                    if des_iface.is_ignore() {
                        full_ignores.insert(iface.name());
                    }
                }
                None => {
                    not_desired_ignores.insert(iface.name());
                    full_ignores.insert(iface.name());
                }
            }
        }
        for iface in self.kernel_ifaces.values().filter(|i| i.is_ignore()) {
            full_ignores.insert(iface.name());
        }

        // Contains interface names need to be marked as `state: up` afterwards.
        let mut pending_changes: Vec<String> = Vec::new();

        for iface in self
            .kernel_ifaces
            .values()
            .filter(|i| i.is_controller() && i.is_up())
        {
            let cur_iface = current.get_iface(iface.name(), iface.iface_type());
            if let Some(port_names) = iface.ports() {
                for port_name in port_names {
                    if not_desired_ignores.contains(port_name) {
                        // Only pre-exist controller holding __no__
                        // ignored ports can fit our auto-fix case.
                        // Or new interface.
                        if cur_iface.and_then(|i| i.ports()).map(|cur_ports| {
                            cur_ports
                                .as_slice()
                                .iter()
                                .any(|cur_port| full_ignores.contains(cur_port))
                        }) != Some(true)
                        {
                            log::info!(
                                "Controller interface {}({}) contains \
                                port {port_name} which is currently ignored, \
                                marking this port as 'state: up'. ",
                                iface.name(),
                                iface.iface_type()
                            );
                            pending_changes.push(port_name.to_string());
                        }
                    }
                }
            }
        }

        for iface_name in pending_changes {
            if let Some(cur_iface) =
                current.kernel_ifaces.get(iface_name.as_str())
            {
                let mut iface = cur_iface.clone_name_type_only();
                iface.base_iface_mut().state = InterfaceState::Up;
                self.kernel_ifaces.insert(iface_name, iface);
            }
        }
    }
}
