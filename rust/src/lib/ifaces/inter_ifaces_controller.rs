use std::collections::{HashMap, HashSet};
use std::iter::FromIterator;

use log::{debug, error, info};

use crate::{
    ErrorKind, InterfaceState, InterfaceType, Interfaces, NmstateError,
};

pub(crate) fn handle_changed_ports(
    ifaces: &mut Interfaces,
    cur_ifaces: &Interfaces,
) -> Result<(), NmstateError> {
    let mut pending_changes: HashMap<
        String,
        (Option<String>, Option<InterfaceType>),
    > = HashMap::new();
    for (iface_name, iface) in ifaces.kernel_ifaces.iter() {
        if !iface.is_up() {
            continue;
        }
        let desire_port_names = match iface.ports() {
            Some(p) => HashSet::from_iter(p.iter().cloned()),
            None => continue,
        };
        let current_port_names = match cur_ifaces.kernel_ifaces.get(iface_name)
        {
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
                (Some(iface_name.to_string()), Some(iface.iface_type())),
            );
        }

        // Detaching port from current controller
        for port_name in current_port_names.difference(&desire_port_names) {
            pending_changes.insert(port_name.to_string(), (None, None));
        }

        // Set controller property if port in desire
        for port_name in current_port_names.intersection(&desire_port_names) {
            if ifaces.kernel_ifaces.contains_key(&port_name.to_string()) {
                pending_changes.insert(
                    port_name.to_string(),
                    (Some(iface_name.to_string()), Some(iface.iface_type())),
                );
            }
        }
    }

    for (iface_name, (ctrl_name, ctrl_type)) in pending_changes.drain() {
        match ifaces.kernel_ifaces.get_mut(&iface_name) {
            Some(iface) => {
                iface.base_iface_mut().controller = ctrl_name;
                iface.base_iface_mut().controller_type = ctrl_type;
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
                        iface.base_iface_mut().state = InterfaceState::Up;
                        iface.base_iface_mut().controller = ctrl_name;
                        iface.base_iface_mut().controller_type = ctrl_type;
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
    Ok(())
}

// TODO: user space interfaces
pub(crate) fn set_ifaces_up_priority(ifaces: &mut Interfaces) -> bool {
    // Return true when all interface has correct priority.
    let mut ret = true;
    let mut pending_changes: HashMap<String, u32> = HashMap::new();
    // Use the push order to allow user providing help on dependency order
    for (iface_name, _) in &ifaces.insert_order {
        let iface = match ifaces.kernel_ifaces.get(iface_name) {
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
            if let Some(ctrl_iface) =
                ifaces.kernel_ifaces.get(ctrl_name.as_str())
            {
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

// Instead of placing tests in `tests` folder, we can test pub(crate) functions
// here
#[cfg(test)]
mod tests {
    use crate::{
        ErrorKind, EthernetInterface, Interface, InterfaceType, Interfaces,
        LinuxBridgeInterface,
    };

    #[test]
    fn test_ifaces_up_order_no_ctrler_reserse_order() {
        let mut ifaces = Interfaces::new();
        ifaces.push(new_eth_iface("eth2"));
        ifaces.push(new_eth_iface("eth1"));

        let (add_ifaces, _, _) =
            ifaces.gen_state_for_apply(&Interfaces::new()).unwrap();

        assert_eq!(ifaces.kernel_ifaces["eth1"].base_iface().up_priority, 0);
        assert_eq!(ifaces.kernel_ifaces["eth2"].base_iface().up_priority, 0);

        let ordered_ifaces = add_ifaces.to_vec();
        assert_eq!(ordered_ifaces[0].name(), "eth1".to_string());
        assert_eq!(ordered_ifaces[1].name(), "eth2".to_string());
    }

    #[test]
    fn test_ifaces_up_order_nested_4_depth_worst_case() {
        let mut ifaces = Interfaces::new();

        let [br0, br1, br2, br3, p1, p2] = new_nested_4_ifaces();

        // Push with reverse order which is the worst case
        ifaces.push(p2);
        ifaces.push(p1);
        ifaces.push(br3);
        ifaces.push(br2);
        ifaces.push(br1);
        ifaces.push(br0);

        let (add_ifaces, _, _) =
            ifaces.gen_state_for_apply(&Interfaces::new()).unwrap();

        assert_eq!(ifaces.kernel_ifaces["br0"].base_iface().up_priority, 0);
        assert_eq!(ifaces.kernel_ifaces["br1"].base_iface().up_priority, 1);
        assert_eq!(ifaces.kernel_ifaces["br2"].base_iface().up_priority, 2);
        assert_eq!(ifaces.kernel_ifaces["br3"].base_iface().up_priority, 3);
        assert_eq!(ifaces.kernel_ifaces["p1"].base_iface().up_priority, 4);
        assert_eq!(ifaces.kernel_ifaces["p2"].base_iface().up_priority, 4);

        let ordered_ifaces = add_ifaces.to_vec();

        assert_eq!(ordered_ifaces[0].name(), "br0".to_string());
        assert_eq!(ordered_ifaces[1].name(), "br1".to_string());
        assert_eq!(ordered_ifaces[2].name(), "br2".to_string());
        assert_eq!(ordered_ifaces[3].name(), "br3".to_string());
        assert_eq!(ordered_ifaces[4].name(), "p1".to_string());
        assert_eq!(ordered_ifaces[5].name(), "p2".to_string());
    }

    #[test]
    fn test_ifaces_up_order_nested_5_depth_worst_case() {
        let mut ifaces = Interfaces::new();
        let [_, br1, br2, br3, p1, p2] = new_nested_4_ifaces();

        let br4 = new_br_ifaces("br4");
        let mut br0 = new_br_ifaces("br0");

        br0.base_iface_mut().controller = Some("br4".to_string());
        br0.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);

        // Push with reverse order which is the worst case
        ifaces.push(p1);
        ifaces.push(p2);
        ifaces.push(br3);
        ifaces.push(br2);
        ifaces.push(br1);
        ifaces.push(br0);
        ifaces.push(br4);

        let result = ifaces.gen_state_for_apply(&Interfaces::new());
        assert!(result.is_err());

        if let Err(e) = result {
            assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        }
    }

    #[test]
    fn test_ifaces_up_order_nested_5_depth_good_case() {
        let mut ifaces = Interfaces::new();
        let [_, br1, br2, br3, p1, p2] = new_nested_4_ifaces();

        let br4 = new_br_ifaces("br4");
        let mut br0 = new_br_ifaces("br0");

        br0.base_iface_mut().controller = Some("br4".to_string());
        br0.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);

        ifaces.push(br4);
        ifaces.push(br0);
        ifaces.push(br1);
        ifaces.push(br2);
        ifaces.push(br3);
        ifaces.push(p2);
        ifaces.push(p1);

        let (add_ifaces, _, _) =
            ifaces.gen_state_for_apply(&Interfaces::new()).unwrap();

        assert_eq!(ifaces.kernel_ifaces["br4"].base_iface().up_priority, 0);
        assert_eq!(ifaces.kernel_ifaces["br0"].base_iface().up_priority, 1);
        assert_eq!(ifaces.kernel_ifaces["br1"].base_iface().up_priority, 2);
        assert_eq!(ifaces.kernel_ifaces["br2"].base_iface().up_priority, 3);
        assert_eq!(ifaces.kernel_ifaces["br3"].base_iface().up_priority, 4);
        assert_eq!(ifaces.kernel_ifaces["p1"].base_iface().up_priority, 5);
        assert_eq!(ifaces.kernel_ifaces["p2"].base_iface().up_priority, 5);

        let ordered_ifaces = add_ifaces.to_vec();

        assert_eq!(ordered_ifaces[0].name(), "br4".to_string());
        assert_eq!(ordered_ifaces[1].name(), "br0".to_string());
        assert_eq!(ordered_ifaces[2].name(), "br1".to_string());
        assert_eq!(ordered_ifaces[3].name(), "br2".to_string());
        assert_eq!(ordered_ifaces[4].name(), "br3".to_string());
        assert_eq!(ordered_ifaces[5].name(), "p1".to_string());
        assert_eq!(ordered_ifaces[6].name(), "p2".to_string());
    }

    fn new_eth_iface(name: &str) -> Interface {
        let mut iface = EthernetInterface::new();
        iface.base.name = name.to_string();
        Interface::Ethernet(iface)
    }

    fn new_br_ifaces(name: &str) -> Interface {
        let mut iface = LinuxBridgeInterface::new();
        iface.base.name = name.to_string();
        Interface::LinuxBridge(iface)
    }

    fn new_nested_4_ifaces() -> [Interface; 6] {
        let br0 = new_br_ifaces("br0");
        let mut br1 = new_br_ifaces("br1");
        let mut br2 = new_br_ifaces("br2");
        let mut br3 = new_br_ifaces("br3");
        let mut p1 = new_eth_iface("p1");
        let mut p2 = new_eth_iface("p2");

        br1.base_iface_mut().controller = Some("br0".to_string());
        br1.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
        br2.base_iface_mut().controller = Some("br1".to_string());
        br2.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
        br3.base_iface_mut().controller = Some("br2".to_string());
        br3.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
        p1.base_iface_mut().controller = Some("br3".to_string());
        p1.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
        p2.base_iface_mut().controller = Some("br3".to_string());
        p2.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);

        // Place the ifaces in mixed order to complex the work
        [br0, br1, br2, br3, p1, p2]
    }
}
