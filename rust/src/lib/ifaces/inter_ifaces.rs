use std::collections::{hash_map::Entry, HashMap, HashSet};

use log::{debug, error, warn};
use serde::{
    ser::SerializeSeq, Deserialize, Deserializer, Serialize, Serializer,
};

use crate::{
    ErrorKind, Interface, InterfaceState, InterfaceType, NmstateError,
};

#[derive(Clone, Debug, Default)]
pub struct Interfaces {
    pub(crate) kernel_ifaces: HashMap<String, Interface>,
    pub(crate) user_ifaces: HashMap<(String, InterfaceType), Interface>,
}

impl<'de> Deserialize<'de> for Interfaces {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let mut ret = Self::new();
        let ifaces =
            <Vec<Interface> as Deserialize>::deserialize(deserializer)?;
        for iface in ifaces {
            ret.push(iface)
        }
        Ok(ret)
    }
}

impl Serialize for Interfaces {
    // Serialize is also used for verification.
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let ifaces = self.to_vec();
        let mut seq = serializer.serialize_seq(Some(ifaces.len()))?;
        for iface in ifaces {
            seq.serialize_element(iface)?;
        }
        seq.end()
    }
}

impl Interfaces {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn to_vec(&self) -> Vec<&Interface> {
        let mut ifaces = Vec::new();
        for iface in self.kernel_ifaces.values() {
            ifaces.push(iface);
        }

        for iface in self.user_ifaces.values() {
            ifaces.push(iface);
        }
        ifaces
    }

    pub fn push(&mut self, iface: Interface) {
        if iface.is_userspace() {
            self.user_ifaces
                .insert((iface.name().to_string(), iface.iface_type()), iface);
        } else {
            self.kernel_ifaces.insert(iface.name().to_string(), iface);
        }
    }

    pub fn update(&mut self, other: &Self) -> Result<(), NmstateError> {
        let mut new_ifaces: Vec<&Interface> = Vec::new();
        let other_ifaces = other.to_vec();
        for other_iface in &other_ifaces {
            // TODO: Handle user space interface
            match self.kernel_ifaces.get_mut(other_iface.name()) {
                Some(self_iface) => {
                    debug!(
                        "Updating interface {:?} with {:?}",
                        self_iface, other_iface
                    );
                    self_iface.update(other_iface);
                }
                None => {
                    debug!("Appending new interface {:?}", other_iface);
                    new_ifaces.push(other_iface);
                }
            }
        }
        Ok(())
    }

    pub(crate) fn verify(
        &self,
        current_ifaces: &Self,
    ) -> Result<(), NmstateError> {
        for iface in self.to_vec() {
            if iface.is_absent() {
                if let Some(cur_iface) =
                    current_ifaces.kernel_ifaces.get(iface.name())
                {
                    if cur_iface.is_virtual() {
                        return Err(NmstateError::new(
                            ErrorKind::VerificationError,
                            format!(
                                "Absent interface {}/{} still found as {:?}",
                                iface.name(),
                                iface.iface_type(),
                                cur_iface
                            ),
                        ));
                    } else if cur_iface.is_up() {
                        let e = NmstateError::new(
                            ErrorKind::VerificationError,
                            format!(
                                "Absent interface {}/{} still found as \
                                state up: {:?}",
                                iface.name(),
                                iface.iface_type(),
                                cur_iface
                            ),
                        );
                        error!("{}", e);
                        return Err(e);
                    }
                }
            } else {
                // TODO: Support user space interface
                if let Some(cur_iface) =
                    current_ifaces.kernel_ifaces.get(iface.name())
                {
                    iface.verify(cur_iface)?;
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
        }
        Ok(())
    }

    pub(crate) fn gen_state_for_apply(
        &self,
        current: &Self,
    ) -> Result<(Self, Self, Self), NmstateError> {
        let mut add_ifaces = Self::new();
        let mut chg_ifaces = Self::new();
        let mut del_ifaces = Self::new();

        for iface in self.to_vec() {
            if !iface.is_absent() {
                match current.kernel_ifaces.get(iface.name()) {
                    Some(cur_iface) => {
                        let mut chg_iface = iface.clone();
                        chg_iface.set_iface_type(cur_iface.iface_type());
                        chg_iface.pre_edit_cleanup()?;
                        chg_ifaces.push(chg_iface);
                    }
                    None => {
                        let mut new_iface = iface.clone();
                        new_iface.pre_edit_cleanup()?;
                        add_ifaces.push(new_iface);
                    }
                }
            } else if let Some(cur_iface) =
                current.kernel_ifaces.get(iface.name())
            {
                if iface.iface_type() != InterfaceType::Unknown
                    && iface.iface_type() != cur_iface.iface_type()
                    && !(cur_iface.iface_type() == InterfaceType::Veth
                        && iface.iface_type() == InterfaceType::Ethernet)
                {
                    warn!(
                        "Interface {} in desire state has different \
                            interface type '{}' than current status '{}'",
                        iface.name(),
                        iface.iface_type(),
                        cur_iface.iface_type()
                    );
                } else {
                    let mut del_iface = cur_iface.clone();
                    del_iface.base_iface_mut().state = InterfaceState::Absent;
                    del_ifaces.push(del_iface);
                }
            }
        }

        handle_changed_ports(&mut add_ifaces, &mut chg_ifaces, current)?;

        //
        // * Set priority to interface base on their child/parent or
        //   subordinate/controller relationships.
        Ok((add_ifaces, chg_ifaces, del_ifaces))
    }
}

// Include changed subordinates to chg_ifaces
// TODO: Support nested bridge/bond/etc
fn handle_changed_ports(
    add_ifaces: &mut Interfaces,
    chg_ifaces: &mut Interfaces,
    cur_ifaces: &Interfaces,
) -> Result<(), NmstateError> {
    let mut changed_ports_to_ctrl: HashMap<String, (String, InterfaceType)> =
        HashMap::new();
    let mut detaching_port_names: Vec<String> = Vec::new();

    for iface in add_ifaces.to_vec() {
        if let Some(port_names) = iface.ports() {
            for port_name in port_names {
                changed_ports_to_ctrl.insert(
                    port_name.to_string(),
                    (iface.name().to_string(), iface.iface_type()),
                );
            }
        }
    }

    for iface in chg_ifaces.to_vec() {
        if let Some(port_names) = iface.ports() {
            let mut desire_port_names: HashSet<String> = HashSet::new();
            for port_name in port_names {
                desire_port_names.insert(port_name.to_string());
            }
            let mut current_port_names: HashSet<String> = HashSet::new();
            if let Some(cur_iface) = cur_ifaces.kernel_ifaces.get(iface.name())
            {
                if let Some(cur_port_names) = cur_iface.ports() {
                    for port_name in cur_port_names {
                        current_port_names.insert(port_name.to_string());
                    }
                }
            }

            // Attaching new port to controller
            for port_name in desire_port_names.difference(&current_port_names) {
                if let Some((ctrl_name, _)) =
                    changed_ports_to_ctrl.get(port_name)
                {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Port {} cannot be assigned to \
                                two controller: {} {}",
                            port_name,
                            ctrl_name,
                            iface.name()
                        ),
                    ));
                } else {
                    changed_ports_to_ctrl.insert(
                        port_name.to_string(),
                        (iface.name().to_string(), iface.iface_type()),
                    );
                }
            }

            // Detaching port from current controller
            for port_name in current_port_names.difference(&desire_port_names) {
                // This port might move from controller to another,
                // we have to process it later after this stage
                detaching_port_names.push(port_name.to_string());
            }
        }
    }

    for detach_port_name in &detaching_port_names {
        if !changed_ports_to_ctrl.contains_key(detach_port_name) {
            // Port is detached from any controller
            match chg_ifaces.kernel_ifaces.entry(detach_port_name.to_string()) {
                Entry::Occupied(o) => {
                    let iface = o.into_mut();
                    iface.base_iface_mut().controller = None;
                    iface.base_iface_mut().controller_type = None;
                }
                Entry::Vacant(v) => {
                    if let Some(cur_iface) =
                        cur_ifaces.kernel_ifaces.get(detach_port_name)
                    {
                        if cur_iface.base_iface().controller != None {
                            let mut iface = cur_iface.clone();
                            iface.base_iface_mut().controller = None;
                            iface.base_iface_mut().controller_type = None;
                            v.insert(iface);
                        }
                    }
                }
            };
        }
    }

    for (port_name, (ctrl_name, ctrl_type)) in changed_ports_to_ctrl.iter() {
        if let Some(cur_iface) = cur_ifaces.kernel_ifaces.get(port_name) {
            match chg_ifaces.kernel_ifaces.entry(port_name.to_string()) {
                Entry::Occupied(o) => {
                    let iface = o.into_mut();
                    iface.base_iface_mut().controller =
                        Some(ctrl_name.to_string());
                    iface.base_iface_mut().controller_type =
                        Some(ctrl_type.clone());
                }
                Entry::Vacant(v) => {
                    let mut iface = cur_iface.clone();
                    iface.base_iface_mut().controller =
                        Some(ctrl_name.to_string());
                    iface.base_iface_mut().controller_type =
                        Some(ctrl_type.clone());
                    v.insert(iface);
                }
            }
        } else if let Some(iface) = add_ifaces.kernel_ifaces.get_mut(port_name)
        {
            iface.base_iface_mut().controller = Some(ctrl_name.to_string());
            iface.base_iface_mut().controller_type = Some(ctrl_type.clone());
        } else {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Port {} of {} interface {} not found in system or \
                            new desire state",
                    port_name, ctrl_type, ctrl_name
                ),
            ));
        }
    }
    Ok(())
}
