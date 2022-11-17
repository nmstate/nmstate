// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde::{
    ser::SerializeSeq, Deserialize, Deserializer, Serialize, Serializer,
};

use crate::{
    ifaces::ethernet::handle_veth_peer_changes,
    ifaces::inter_ifaces_controller::{
        check_infiniband_as_ports, check_overbook_ports, handle_changed_ports,
        preserve_ctrl_cfg_if_unchanged, set_ifaces_up_priority,
        validate_new_ovs_iface_has_controller,
    },
    ifaces::sriov::check_sriov_capability,
    ErrorKind, Interface, InterfaceState, InterfaceType, NmstateError,
};

// The max loop count for Interfaces.set_up_priority()
// This allows interface with 4 nested levels in any order.
// To support more nested level, user could place top controller at the
// beginning of desire state
const INTERFACES_SET_PRIORITY_MAX_RETRY: u32 = 4;

const COPY_MAC_ALLOWED_IFACE_TYPES: [InterfaceType; 3] = [
    InterfaceType::Bond,
    InterfaceType::LinuxBridge,
    InterfaceType::OvsInterface,
];

#[derive(Clone, Debug, Default, PartialEq, Eq)]
#[non_exhaustive]
/// Represent a list of [Interface] with special [serde::Deserializer] and
/// [serde::Serializer].
/// When applying complex nested interface(e.g. bridge over bond over vlan of
/// eth1), the supported maximum nest level is 4 like previous example.
/// For 5+ nested level, you need to place controller interface before its
/// ports.
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
        for iface in <Vec<Interface> as Deserialize>::deserialize(deserializer)?
        {
            ret.push(iface);
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
    /// Create empty [Interfaces].
    pub fn new() -> Self {
        Self::default()
    }

    pub fn is_empty(&self) -> bool {
        self.kernel_ifaces.is_empty() && self.user_ifaces.is_empty()
    }

    /// Extract internal interfaces to `Vec()`.
    pub fn to_vec(&self) -> Vec<&Interface> {
        let mut ifaces = Vec::new();
        for iface in self.kernel_ifaces.values() {
            ifaces.push(iface);
        }
        for iface in self.user_ifaces.values() {
            ifaces.push(iface);
        }
        ifaces.sort_unstable_by_key(|iface| iface.name());
        // Use sort_by_key() instead of unstable one, do we can alphabet
        // activation order which is required to simulate the OS boot-up.
        ifaces.sort_by_key(|iface| iface.base_iface().up_priority);

        ifaces
    }

    /// Search interface base on interface name and interface type.
    /// When using [InterfaceType::Unknown], we only search kernel
    /// interface(which has presentation in kernel space).
    pub fn get_iface<'a, 'b>(
        &'a self,
        iface_name: &'b str,
        iface_type: InterfaceType,
    ) -> Option<&'a Interface> {
        if iface_type == InterfaceType::Unknown {
            self.kernel_ifaces.get(&iface_name.to_string()).or_else(|| {
                self.user_ifaces
                    .values()
                    .find(|&iface| iface.name() == iface_name)
            })
        } else if iface_type.is_userspace() {
            self.user_ifaces.get(&(iface_name.to_string(), iface_type))
        } else {
            self.kernel_ifaces.get(&iface_name.to_string())
        }
    }

    /// Append specified [Interface].
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

    pub(crate) fn gen_state_for_apply(
        &mut self,
        current: &Self,
        memory_only: bool,
    ) -> Result<(Self, Self, Self), NmstateError> {
        let mut add_ifaces = Self::new();
        let mut chg_ifaces = Self::new();
        let mut del_ifaces = Self::new();
        let mut new_ovs_ifaces = Vec::new();

        self.apply_copy_mac_from(current)?;
        self.validate_controller_and_port_list_confliction()?;
        handle_changed_ports(self, current)?;
        preserve_ctrl_cfg_if_unchanged(self, current);
        self.set_up_priority()?;
        check_overbook_ports(self, current)?;
        check_infiniband_as_ports(self, current)?;
        if !current.kernel_ifaces.is_empty() {
            check_sriov_capability(self)?;
        }

        for iface in self.to_vec() {
            if iface.is_absent() {
                for del_iface in gen_ifaces_to_del(iface, current) {
                    del_ifaces.push(del_iface);
                }
            } else {
                match current.get_iface(iface.name(), iface.iface_type()) {
                    Some(cur_iface) => {
                        let mut chg_iface = iface.clone();
                        if cur_iface.iface_type() == InterfaceType::Unknown {
                            chg_iface.set_iface_type(cur_iface.iface_type());
                        }
                        chg_iface.pre_edit_cleanup(Some(cur_iface))?;
                        log::info!(
                            "Changing interface {} with type {}, \
                            up priority {}",
                            chg_iface.name(),
                            chg_iface.iface_type(),
                            chg_iface.base_iface().up_priority
                        );
                        chg_ifaces.push(chg_iface);
                    }
                    None => {
                        let mut new_iface = iface.clone();
                        new_iface.pre_edit_cleanup(None)?;
                        log::info!(
                            "Adding interface {} with type {}, \
                            up priority {}",
                            new_iface.name(),
                            new_iface.iface_type(),
                            new_iface.base_iface().up_priority
                        );
                        // When adding new OVS interface requires changes to
                        // existing OVS bridge, we should place this new OVS
                        // interface along with its controller -- chg_ifaces.
                        if new_iface.iface_type() == InterfaceType::OvsInterface
                            || new_iface.base_iface().controller_type
                                == Some(InterfaceType::OvsBridge)
                        {
                            new_ovs_ifaces.push(new_iface.clone());
                            if new_iface
                                .base_iface()
                                .controller
                                .as_ref()
                                .and_then(|br_name| {
                                    current.get_iface(
                                        br_name,
                                        InterfaceType::OvsBridge,
                                    )
                                })
                                .is_some()
                            {
                                chg_ifaces.push(new_iface);
                            } else {
                                add_ifaces.push(new_iface);
                            }
                        } else {
                            add_ifaces.push(new_iface);
                        }
                    }
                }
            }
        }

        mark_orphan_interface_as_absent(&mut del_ifaces, &chg_ifaces, current);
        handle_veth_peer_changes(
            &add_ifaces,
            &mut chg_ifaces,
            &mut del_ifaces,
            current,
        )?;
        validate_new_ovs_iface_has_controller(&new_ovs_ifaces, self, current)?;

        if memory_only {
            // In memory_only mode, absent interface equal to down
            // action.
            for iface in del_ifaces.to_vec() {
                let mut chg_iface = iface.clone();
                chg_iface.base_iface_mut().state = InterfaceState::Down;
                log::info!(
                    "In memory only mode, state absent is treated \
                    as state down for interface: {}/{:?}",
                    iface.name(),
                    iface.iface_type()
                );
                chg_ifaces.push(chg_iface);
            }
            del_ifaces.kernel_ifaces = Default::default();
            del_ifaces.user_ifaces = Default::default();
        }

        Ok((add_ifaces, chg_ifaces, del_ifaces))
    }

    /// TODO: this is internal function.
    pub fn set_up_priority(&mut self) -> Result<(), NmstateError> {
        for _ in 0..INTERFACES_SET_PRIORITY_MAX_RETRY {
            if set_ifaces_up_priority(self) {
                return Ok(());
            }
        }
        log::error!(
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

    fn apply_copy_mac_from(
        &mut self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        for (iface_name, iface) in self.kernel_ifaces.iter_mut() {
            if !COPY_MAC_ALLOWED_IFACE_TYPES.contains(&iface.iface_type()) {
                continue;
            }
            if let Some(src_iface_name) = &iface.base_iface().copy_mac_from {
                if let Some(cur_iface) =
                    current.kernel_ifaces.get(src_iface_name)
                {
                    if !is_opt_str_empty(
                        &cur_iface.base_iface().permanent_mac_address,
                    ) {
                        iface.base_iface_mut().mac_address = cur_iface
                            .base_iface()
                            .permanent_mac_address
                            .clone();
                    } else if !is_opt_str_empty(
                        &cur_iface.base_iface().mac_address,
                    ) {
                        iface.base_iface_mut().mac_address =
                            cur_iface.base_iface().mac_address.clone();
                    } else {
                        let e = NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Failed to find mac address of interface {} \
                                for copy-mac-from of iface {}",
                                src_iface_name, iface_name
                            ),
                        );
                        log::error!("{}", e);
                        return Err(e);
                    }
                } else {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Failed to find interface {} for \
                            copy-mac-from of iface {}",
                            src_iface_name, iface_name
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
        }
        Ok(())
    }

    pub(crate) fn hide_secrets(&mut self) {
        for iface in self.kernel_ifaces.values_mut() {
            iface.base_iface_mut().hide_secrets();
        }
    }
}

fn gen_ifaces_to_del(
    del_iface: &Interface,
    cur_ifaces: &Interfaces,
) -> Vec<Interface> {
    let mut del_ifaces = Vec::new();
    let cur_ifaces = cur_ifaces.to_vec();
    for cur_iface in cur_ifaces {
        let del_iface_type = match del_iface.iface_type() {
            InterfaceType::Veth => InterfaceType::Ethernet,
            t => t,
        };
        let cur_iface_type = match cur_iface.iface_type() {
            InterfaceType::Veth => InterfaceType::Ethernet,
            t => t,
        };
        if cur_iface.name() == del_iface.name()
            && (del_iface_type == InterfaceType::Unknown
                || del_iface_type == cur_iface_type)
        {
            let mut tmp_iface = del_iface.clone();
            tmp_iface.base_iface_mut().iface_type = cur_iface.iface_type();
            log::info!(
                "Deleting interface {}/{}",
                tmp_iface.name(),
                tmp_iface.iface_type()
            );
            del_ifaces.push(tmp_iface);
        }
    }
    if del_ifaces.is_empty() {
        log::info!(
            "Interface {} does not exists, requesting configuration purge",
            del_iface.name()
        );
        del_ifaces.push(del_iface.clone());
    }
    del_ifaces
}

fn is_opt_str_empty(opt_string: &Option<String>) -> bool {
    if let Some(s) = opt_string {
        s.is_empty()
    } else {
        true
    }
}

fn mark_orphan_interface_as_absent(
    del_ifaces: &mut Interfaces,
    chg_ifaces: &Interfaces,
    current: &Interfaces,
) {
    for cur_iface in current.kernel_ifaces.values() {
        let parent = if let Some(chg_iface) =
            chg_ifaces.kernel_ifaces.get(cur_iface.name())
        {
            chg_iface.parent()
        } else {
            cur_iface.parent()
        };
        if let Some(parent) = parent {
            if del_ifaces.kernel_ifaces.get(parent).is_some()
                && del_ifaces.kernel_ifaces.get(cur_iface.name()).is_none()
            {
                let mut new_iface = cur_iface.clone_name_type_only();
                new_iface.base_iface_mut().state = InterfaceState::Absent;
                log::info!(
                    "Marking interface {} as absent as its parent {} is so",
                    cur_iface.name(),
                    parent
                );
                del_ifaces.push(new_iface);
            }
        }
    }
}
