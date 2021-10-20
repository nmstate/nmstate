use std::collections::HashMap;

use log::{debug, error, info, warn};
use serde::{
    ser::SerializeSeq, Deserialize, Deserializer, Serialize, Serializer,
};

use crate::{
    ifaces::inter_ifaces_controller::{
        handle_changed_ports, set_ifaces_up_priority,
    },
    ErrorKind, Interface, InterfaceState, InterfaceType, NmstateError,
};

// The max loop count for Interfaces.set_up_priority()
// This allows interface with 4 nested levels in any order.
// To support more nested level, user could place top controller at the
// beginning of desire state
const INTERFACES_SET_PRIORITY_MAX_RETRY: u32 = 4;

#[derive(Clone, Debug, Default)]
pub struct Interfaces {
    pub(crate) kernel_ifaces: HashMap<String, Interface>,
    pub(crate) user_ifaces: HashMap<(String, InterfaceType), Interface>,
    // The insert_order is allowing user to provided ordered interface
    // to support 5+ nested dependency.
    pub(crate) insert_order: Vec<(String, InterfaceType)>,
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
        ifaces.sort_unstable_by_key(|iface| iface.name());
        // Use sort_by_key() instead of unstable one, do we can alphabet
        // activation order which is required to simulate the OS boot-up.
        ifaces.sort_by_key(|iface| iface.base_iface().up_priority);

        for iface in self.user_ifaces.values() {
            ifaces.push(iface);
        }
        ifaces
    }

    pub fn push(&mut self, iface: Interface) {
        self.insert_order
            .push((iface.name().to_string(), iface.iface_type()));
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
                        "Merging interface {:?} into {:?}",
                        other_iface, self_iface
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
        &mut self,
        current: &Self,
    ) -> Result<(Self, Self, Self), NmstateError> {
        let mut add_ifaces = Self::new();
        let mut chg_ifaces = Self::new();
        let mut del_ifaces = Self::new();

        handle_changed_ports(self, current)?;
        self.set_up_priority()?;

        for iface in self.to_vec() {
            if !iface.is_absent() {
                match current.kernel_ifaces.get(iface.name()) {
                    Some(cur_iface) => {
                        let mut chg_iface = iface.clone();
                        chg_iface.set_iface_type(cur_iface.iface_type());
                        chg_iface.pre_edit_cleanup()?;
                        info!(
                            "Changing interface {} with type {}",
                            chg_iface.name(),
                            chg_iface.iface_type()
                        );
                        chg_ifaces.push(chg_iface);
                    }
                    None => {
                        let mut new_iface = iface.clone();
                        new_iface.pre_edit_cleanup()?;
                        info!(
                            "Adding interface {} with type {}",
                            new_iface.name(),
                            new_iface.iface_type()
                        );
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
                    info!(
                        "Deleting interface {} with type {}",
                        del_iface.name(),
                        del_iface.iface_type()
                    );
                    del_ifaces.push(del_iface);
                }
            }
        }

        Ok((add_ifaces, chg_ifaces, del_ifaces))
    }

    pub fn set_up_priority(&mut self) -> Result<(), NmstateError> {
        for _ in 0..INTERFACES_SET_PRIORITY_MAX_RETRY {
            if set_ifaces_up_priority(self) {
                return Ok(());
            }
        }
        error!(
            "Failed to set up priority: please order the interfaces in desire \
            state to place controller before its ports"
        );
        Err(NmstateError::new(
            ErrorKind::InvalidArgument,
            "Failed to set up priority: nmstate only support nested interface \
            up to 4 levels. To support more nest level, \
            please order the interfaces in desire \
            state to place controller before its ports"
                .to_string(),
        ))
    }
}
