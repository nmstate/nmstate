use std::collections::{HashMap, HashSet};
use std::iter::FromIterator;

use log::{debug, error, info};

use crate::{
    BaseInterface, ErrorKind, Interface, InterfaceIpv4, InterfaceIpv6,
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
                if iface.need_controller() && ctrl_name.is_none() {
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
                    if cur_iface.base_iface().controller != ctrl_name
                        || cur_iface.base_iface().controller_type != ctrl_type
                    {
                        let mut iface = cur_iface.clone();
                        // Some interface cannot live without controller
                        if iface.need_controller() && ctrl_name.is_none() {
                            iface.base_iface_mut().state =
                                InterfaceState::Absent;
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
                    }
                } else {
                    // Do not raise error if detach port
                    if let Some(ctrl_name) = ctrl_name {
                        // OVS internal interface could be created without
                        // been defined in desire or current state
                        if let Some(InterfaceType::OvsBridge) = ctrl_type {
                            ifaces.push(gen_ovs_interface(
                                &iface_name,
                                &ctrl_name,
                            ));
                            info!(
                                "Include OVS internal interface {} to edit \
                                as its controller required so",
                                iface_name
                            );
                        } else {
                            return Err(NmstateError::new(
                                ErrorKind::InvalidArgument,
                                format!(
                                    "Interface {} is holding unknown port {}",
                                    ctrl_name, iface_name
                                ),
                            ));
                        }
                    }
                }
            }
        }
    }
    Ok(())
}

fn gen_ovs_interface(iface_name: &str, ctrl_name: &str) -> Interface {
    let mut base_iface = BaseInterface::new();
    base_iface.name = iface_name.to_string();
    base_iface.iface_type = InterfaceType::OvsInterface;
    base_iface.controller = Some(ctrl_name.to_string());
    base_iface.controller_type = Some(InterfaceType::OvsBridge);
    Interface::OvsInterface({
        let mut iface = OvsInterface::new();
        iface.base = base_iface;
        iface
    })
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
        None => return Ok(()),
    };
    let current_port_names =
        match cur_ifaces.kernel_ifaces.get(iface.name()).or_else(|| {
            cur_ifaces
                .user_ifaces
                .get(&(iface.name().to_string(), iface.iface_type()))
        }) {
            Some(cur_iface) => match cur_iface.ports() {
                Some(p) => HashSet::from_iter(p.iter().cloned()),
                None => HashSet::new(),
            },
            None => HashSet::new(),
        };

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
            .or_insert_with(|| (None, None));
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
                // There will be other validator check missing
                // controller
                error!("BUG: _set_up_priority() got port without controller");
                continue;
            }
        } else {
            continue;
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

pub(crate) fn find_unknown_type_port<'a>(
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
