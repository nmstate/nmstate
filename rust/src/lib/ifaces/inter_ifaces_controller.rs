// SPDX-License-Identifier: Apache-2.0

use std::collections::{HashMap, HashSet};
use std::iter::FromIterator;

use log::{debug, info};

use crate::{
    BondMode, ErrorKind, Interface, InterfaceIpv4, InterfaceIpv6,
    InterfaceState, InterfaceType, Interfaces, NmstateError, OvsInterface,
};

pub(crate) fn handle_changed_ports(
    ifaces: &mut Interfaces,
    cur_ifaces: &Interfaces,
) -> Result<(), NmstateError> {
    let mut pending_changes: HashMap<
        String,
        (Option<String>, Option<InterfaceType>),
    > = HashMap::new();
    for iface in ifaces.kernel_ifaces.values() {
        if !iface.is_controller() {
            continue;
        }
        handle_changed_ports_of_iface(
            iface,
            ifaces,
            cur_ifaces,
            &mut pending_changes,
        )?;
    }

    for iface in ifaces.user_ifaces.values() {
        if !iface.is_controller() {
            continue;
        }
        handle_changed_ports_of_iface(
            iface,
            ifaces,
            cur_ifaces,
            &mut pending_changes,
        )?;
    }

    // Linux Bridge might have changed configure its port configuration with
    // port name list unchanged.
    // In this case, we should ask LinuxBridgeInterface to generate a list
    // of configure changed port.
    for iface in ifaces
        .kernel_ifaces
        .values()
        .filter(|i| i.is_up() && i.iface_type() == InterfaceType::LinuxBridge)
    {
        if let Some(Interface::LinuxBridge(cur_iface)) =
            cur_ifaces.get_iface(iface.name(), InterfaceType::LinuxBridge)
        {
            if let Interface::LinuxBridge(br_iface) = iface {
                for port_name in br_iface.get_config_changed_ports(cur_iface) {
                    pending_changes.insert(
                        port_name.to_string(),
                        (
                            Some(iface.name().to_string()),
                            Some(InterfaceType::LinuxBridge),
                        ),
                    );
                }
            }
        }
    }

    for (iface_name, (ctrl_name, ctrl_type)) in pending_changes.drain() {
        match ifaces.kernel_ifaces.get_mut(&iface_name) {
            Some(iface) => {
                // Some interface cannot live without controller
                if iface.need_controller()
                    && (ctrl_name.as_ref().map(|n| n.is_empty()) != Some(false))
                {
                    iface.base_iface_mut().state = InterfaceState::Absent;
                } else {
                    iface.base_iface_mut().controller = ctrl_name;
                    iface.base_iface_mut().controller_type = ctrl_type;
                }
            }
            None => {
                // Port not found in desired state
                if let Some(cur_iface) =
                    cur_ifaces.kernel_ifaces.get(&iface_name)
                {
                    let mut iface = cur_iface.clone_name_type_only();
                    // Some interface cannot live without controller
                    if iface.need_controller()
                        && (ctrl_name.as_ref().map(|n| n.is_empty())
                            != Some(false))
                    {
                        iface.base_iface_mut().state = InterfaceState::Absent;
                    } else {
                        iface.base_iface_mut().state = InterfaceState::Up;
                    }
                    iface.base_iface_mut().controller = ctrl_name;
                    iface.base_iface_mut().controller_type = ctrl_type;
                    if !iface.base_iface().can_have_ip() {
                        iface.base_iface_mut().ipv4 =
                            Some(InterfaceIpv4::new());
                        iface.base_iface_mut().ipv6 =
                            Some(InterfaceIpv6::new());
                    }
                    info!(
                        "Include interface {} to edit as its \
                        controller required so",
                        iface_name
                    );
                    ifaces.push(iface);
                } else {
                    // Do not raise error if detach port
                    if let Some(ctrl_name) = ctrl_name {
                        if !ctrl_name.is_empty() {
                            // OVS internal interface could be created without
                            // been defined in desire or current state
                            if let Some(InterfaceType::OvsBridge) = ctrl_type {
                                ifaces.push(Interface::OvsInterface(
                                    OvsInterface::new_with_name_and_ctrl(
                                        &iface_name,
                                        &ctrl_name,
                                    ),
                                ));
                                info!(
                                    "Include OVS internal interface {} to \
                                    edit as its controller required so",
                                    iface_name
                                );
                            } else {
                                return Err(NmstateError::new(
                                    ErrorKind::InvalidArgument,
                                    format!(
                                        "Interface {ctrl_name} is holding unknown \
                                        port {iface_name}"
                                    ),
                                ));
                            }
                        }
                    }
                }
            }
        }
    }
    // When only port iface with `controller` peppery without its controller
    // interface been mentioned in desired state, we need to resolve its
    // controller type for backend to proceed.
    resolve_port_iface_controller_type(ifaces, cur_ifaces)?;

    Ok(())
}

fn handle_changed_ports_of_iface(
    iface: &Interface,
    ifaces: &Interfaces,
    cur_ifaces: &Interfaces,
    pending_changes: &mut HashMap<
        String,
        (Option<String>, Option<InterfaceType>),
    >,
) -> Result<(), NmstateError> {
    let desire_port_names = match iface.ports() {
        Some(p) => HashSet::from_iter(p.iter().cloned()),
        None => {
            if let Some(cur_iface) =
                cur_ifaces.get_iface(iface.name(), iface.iface_type())
            {
                if cur_iface.is_ignore() {
                    // Desire state would like to convert from ignore and
                    // preserving existing port lists
                    match cur_iface.ports().map(|ports| {
                        HashSet::<&str>::from_iter(ports.iter().cloned())
                    }) {
                        Some(p) => p,
                        None => return Ok(()),
                    }
                } else {
                    return Ok(());
                }
            } else {
                return Ok(());
            }
        }
    };

    let current_port_names = cur_ifaces
        .get_iface(iface.name(), iface.iface_type())
        .and_then(|cur_iface| {
            if cur_iface.is_ignore() {
                None
            } else {
                cur_iface.ports()
            }
        })
        .map(|ports| HashSet::<&str>::from_iter(ports.iter().cloned()))
        .unwrap_or_default();

    // Attaching new port to controller
    for port_name in desire_port_names.difference(&current_port_names) {
        pending_changes.insert(
            port_name.to_string(),
            (Some(iface.name().to_string()), Some(iface.iface_type())),
        );
    }

    // Detaching port from current controller
    for port_name in current_port_names.difference(&desire_port_names) {
        // Port might move from one controller to another, if there is already a
        // pending action for this port, we don't override it.
        pending_changes
            .entry(port_name.to_string())
            .or_insert_with(|| (Some("".into()), None));
    }

    // Set controller property if port in desire
    for port_name in current_port_names.intersection(&desire_port_names) {
        if ifaces.kernel_ifaces.contains_key(&port_name.to_string()) {
            pending_changes.insert(
                port_name.to_string(),
                (Some(iface.name().to_string()), Some(iface.iface_type())),
            );
        }
    }

    Ok(())
}

// TODO: user space interfaces
// Return True if we have all up_priority fixed.
pub(crate) fn set_ifaces_up_priority(ifaces: &mut Interfaces) -> bool {
    // Return true when all interface has correct priority.
    let mut ret = true;
    let mut pending_changes: HashMap<String, u32> = HashMap::new();
    // Use the push order to allow user providing help on dependency order
    for (iface_name, iface_type) in &ifaces.insert_order {
        let iface = match ifaces.get_iface(iface_name, iface_type.clone()) {
            Some(i) => i,
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
            let ctrl_iface = ifaces.get_iface(
                ctrl_name,
                iface
                    .base_iface()
                    .controller_type
                    .clone()
                    .unwrap_or_default(),
            );
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
                    debug!(
                        "Controller {} of {} is has no up priority",
                        ctrl_name, iface_name
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
        for (iface_name, iface_type) in &ifaces.insert_order {
            let iface = match ifaces.get_iface(iface_name, iface_type.clone()) {
                Some(i) => i,
                None => continue,
            };
            if !iface.is_up() {
                continue;
            }
            if let Some(parent) = iface.parent() {
                let parent_priority = pending_changes.get(parent).cloned();
                if let Some(parent_priority) = parent_priority {
                    pending_changes
                        .insert(iface_name.to_string(), parent_priority + 1);
                } else if let Some(parent_iface) =
                    ifaces.kernel_ifaces.get(parent)
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

    debug!("pending kernel up priority changes {:?}", pending_changes);
    for (iface_name, priority) in pending_changes.iter() {
        if let Some(iface) = ifaces.kernel_ifaces.get_mut(iface_name) {
            iface.base_iface_mut().up_priority = *priority;
        }
    }

    ret
}

pub(crate) fn check_overbook_ports(
    desired: &Interfaces,
    current: &Interfaces,
) -> Result<(), NmstateError> {
    let mut port_to_ctrl: HashMap<String, String> = HashMap::new();
    for iface in desired
        .kernel_ifaces
        .values()
        .chain(desired.user_ifaces.values())
        .filter(|i| i.is_controller())
    {
        let ports = match iface.ports() {
            Some(p) => p,
            None => {
                // Check whether current interface has ports
                if let Some(cur_iface) =
                    current.get_iface(iface.name(), iface.iface_type())
                {
                    match cur_iface.ports() {
                        Some(p) => p,
                        None => continue,
                    }
                } else {
                    continue;
                }
            }
        };

        for port in ports {
            is_port_overbook(&mut port_to_ctrl, port, iface.name())?;
        }
    }

    Ok(())
}

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

// If any interface has no controller change, copy it from current.
// No controller change means all below:
//  1. Current controller not mentioned in desired.
//  2. Current controller mentioned in desire but hold no port information.
//  3. This interface has no new controller in desired:
pub(crate) fn preserve_ctrl_cfg_if_unchanged(
    ifaces: &mut Interfaces,
    cur_ifaces: &Interfaces,
) {
    let mut desired_ctrls = Vec::new();
    for iface in ifaces
        .kernel_ifaces
        .values()
        .chain(ifaces.user_ifaces.values())
    {
        if iface.is_controller() && iface.ports().is_some() {
            desired_ctrls
                .push((iface.name().to_string(), iface.iface_type().clone()));
        }
    }

    for (iface_name, iface) in ifaces.kernel_ifaces.iter_mut() {
        if (iface.base_iface().controller.is_some()
            && iface.base_iface().controller_type.is_some())
            || iface.base_iface().controller.as_ref() == Some(&String::new())
        {
            // Iface already has controller information or detaching
            continue;
        }
        let cur_iface = match cur_ifaces.kernel_ifaces.get(iface_name) {
            Some(i) => i,
            None => continue,
        };
        if let (Some(ctrl), Some(ctrl_type)) = (
            cur_iface.base_iface().controller.as_ref(),
            cur_iface.base_iface().controller_type.as_ref(),
        ) {
            // If current controller is mentioned in desired, means current
            // interface is been detached.
            if !desired_ctrls.contains(&(ctrl.to_string(), ctrl_type.clone())) {
                iface.base_iface_mut().controller = Some(ctrl.to_string());
                iface.base_iface_mut().controller_type =
                    Some(ctrl_type.clone());
            }
        }
    }
}

// Infiniband over IP can only be port of active_backup bond as it is a layer 3
// interface like tun.
pub(crate) fn check_infiniband_as_ports(
    desired: &Interfaces,
    current: &Interfaces,
) -> Result<(), NmstateError> {
    let ib_iface_names: HashSet<&str> = desired
        .kernel_ifaces
        .values()
        .chain(current.kernel_ifaces.values())
        .filter(|iface| iface.iface_type() == InterfaceType::InfiniBand)
        .map(|iface| iface.name())
        .collect();

    for iface in desired.kernel_ifaces.values().filter(|i| i.is_controller()) {
        if let Some(ports) = iface.ports() {
            let ports = HashSet::from_iter(ports.iter().cloned());
            if !ib_iface_names.is_disjoint(&ports) {
                if let Interface::Bond(iface) = iface {
                    let bond_mode = iface.mode().or_else(|| {
                        if let Some(Interface::Bond(cur_iface)) =
                            current.kernel_ifaces.get(iface.base.name.as_str())
                        {
                            cur_iface.mode()
                        } else {
                            None
                        }
                    });
                    if bond_mode == Some(BondMode::ActiveBackup) {
                        continue;
                    }
                }
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Infiniband interface {:?} cannot use as \
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

// New OVS Interface should have its controller found in desire or current
pub(crate) fn validate_new_ovs_iface_has_controller(
    new_ovs_ifaces: &[Interface],
    desired: &Interfaces,
    current: &Interfaces,
) -> Result<(), NmstateError> {
    for iface in new_ovs_ifaces {
        match iface.base_iface().controller.as_deref() {
            Some(ctrl) => {
                if desired
                    .get_iface(ctrl, InterfaceType::OvsBridge)
                    .or_else(|| {
                        current.get_iface(ctrl, InterfaceType::OvsBridge)
                    })
                    .is_none()
                {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "The controller {} for OVS interface {} does not \
                            exists in current status or desire status",
                            ctrl,
                            iface.name()
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
            None => {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "OVS interface {} does not its OVS bridge defined",
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

fn resolve_port_iface_controller_type(
    ifaces: &mut Interfaces,
    cur_ifaces: &Interfaces,
) -> Result<(), NmstateError> {
    // Port interface can only kernel interface
    for iface in ifaces.kernel_ifaces.values_mut() {
        if let (Some(ctrl_name), None) = (
            iface.base_iface().controller.as_ref(),
            iface.base_iface().controller_type.as_ref(),
        ) {
            if ctrl_name.is_empty() || !iface.is_up() {
                continue;
            }
            // The `handle_changed_ports()` has already set controller type
            // for ports has their controller mentioned in desire state.
            // So here, port interface is referring controller in cur_ifaces
            // state
            match cur_ifaces
                .user_ifaces
                .get(&(ctrl_name.to_string(), InterfaceType::OvsBridge))
                .or_else(|| cur_ifaces.kernel_ifaces.get(ctrl_name))
            {
                Some(ctrl_iface) => {
                    log::debug!(
                        "Setting controller type of interface {} to {}",
                        iface.name(),
                        ctrl_iface.name(),
                    );
                    iface.base_iface_mut().controller_type =
                        Some(ctrl_iface.iface_type())
                }
                None => {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "The controller {} of interface {} \
                            does not exists",
                            ctrl_name,
                            iface.name()
                        ),
                    ));
                }
            }
        }
    }
    Ok(())
}

impl Interfaces {
    // Check whether user defined both controller property and port list of
    // controller interface, examples of invalid desire state:
    //  * eth1 has controller: br1, but br1 has no eth1 in port list
    //  * eth2 has controller: br1, but br2 has eth2 in port list
    //  * eth1 has controller: Some("") (detach), but br1 has eth1 in port list
    pub(crate) fn validate_controller_and_port_list_confliction(
        &self,
    ) -> Result<(), NmstateError> {
        self.valid_controller_not_in_port_list()?;
        self.valid_controller_in_other_port_list()?;
        Ok(())
    }

    fn valid_controller_not_in_port_list(&self) -> Result<(), NmstateError> {
        for iface in self.kernel_ifaces.values() {
            if !iface.is_up() {
                continue;
            }
            if let Some(des_ctrl_name) = iface.base_iface().controller.as_ref()
            {
                if des_ctrl_name.is_empty() {
                    continue;
                } else if let Some(ports) = self
                    .user_ifaces
                    .get(&(des_ctrl_name.to_string(), InterfaceType::OvsBridge))
                    .or_else(|| self.kernel_ifaces.get(des_ctrl_name))
                    .and_then(|ctrl_iface| ctrl_iface.ports())
                {
                    if !ports.contains(&des_ctrl_name.as_str()) {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Interface {} has controller {} \
                                but not listed in port list of controller \
                                interface",
                                iface.name(),
                                des_ctrl_name,
                            ),
                        ));
                    }
                }
            }
        }
        Ok(())
    }

    fn valid_controller_in_other_port_list(&self) -> Result<(), NmstateError> {
        let mut port_to_ctrl = HashMap::new();
        for iface in self.to_vec() {
            if !iface.is_up() {
                continue;
            }
            if let Some(port_names) = iface.ports() {
                for port_name in port_names {
                    port_to_ctrl.insert(port_name, iface.name());
                }
            }
        }
        for iface in self.kernel_ifaces.values() {
            if !iface.is_up() {
                continue;
            }
            if let Some(des_ctrl_name) = iface.base_iface().controller.as_ref()
            {
                if let Some(ctrl_name) = port_to_ctrl.get(iface.name()) {
                    if des_ctrl_name != ctrl_name {
                        if des_ctrl_name.is_empty() {
                            return Err(NmstateError::new(
                                ErrorKind::InvalidArgument,
                                format!(
                                    "Interface {} desired to detach controller \
                                    via controller property set to '', but \
                                    still been listed as port of \
                                    controller {} ",
                                    iface.name(),
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
                                    iface.name(),
                                    des_ctrl_name,
                                    ctrl_name
                                ),
                            ));
                        }
                    }
                }
            }
        }
        Ok(())
    }
}
