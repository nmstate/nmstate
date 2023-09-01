// SPDX-License-Identifier: Apache-2.0

use std::collections::{HashMap, HashSet};
use std::iter::FromIterator;

use serde::{
    ser::SerializeSeq, Deserialize, Deserializer, Serialize, Serializer,
};

use crate::{
    ErrorKind, EthernetInterface, Interface, InterfaceIdentifier,
    InterfaceState, InterfaceType, MergedInterface, NmstateError,
};

// The max loop count for Interfaces.set_ifaces_up_priority()
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
    pub fn get_iface<'a>(
        &'a self,
        iface_name: &str,
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

    fn remove_iface(
        &mut self,
        iface_name: &str,
        iface_type: InterfaceType,
    ) -> Option<Interface> {
        if iface_type == InterfaceType::Unknown {
            self.kernel_ifaces
                .remove(&iface_name.to_string())
                .or_else(|| {
                    if let Some((n, t)) = self
                        .user_ifaces
                        .keys()
                        .find(|&(i, _)| i == iface_name)
                        .cloned()
                    {
                        self.user_ifaces.remove(&(n, t))
                    } else {
                        None
                    }
                })
        } else if iface_type.is_userspace() {
            self.user_ifaces
                .remove(&(iface_name.to_string(), iface_type))
        } else {
            self.kernel_ifaces.remove(&iface_name.to_string())
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

    pub(crate) fn hide_secrets(&mut self) {
        for iface in self.kernel_ifaces.values_mut() {
            iface.base_iface_mut().hide_secrets();
            if let Interface::MacSec(macsec_iface) = iface {
                if let Some(macsec_conf) = macsec_iface.macsec.as_mut() {
                    macsec_conf.hide_secrets();
                }
            }
        }
    }

    pub fn iter(&self) -> impl Iterator<Item = &Interface> {
        self.user_ifaces.values().chain(self.kernel_ifaces.values())
    }

    pub fn iter_mut(&mut self) -> impl Iterator<Item = &mut Interface> {
        self.user_ifaces
            .values_mut()
            .chain(self.kernel_ifaces.values_mut())
    }

    // Not allowing changing veth peer away from ignored peer unless previous
    // peer changed from ignore to managed
    // Not allowing creating veth without peer config
    pub(crate) fn pre_ignore_check(
        &self,
        current: &Self,
        ignored_ifaces: &[(String, InterfaceType)],
    ) -> Result<(), NmstateError> {
        self.validate_change_veth_ignored_peer(current, ignored_ifaces)?;
        self.validate_new_veth_without_peer(current)?;
        Ok(())
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

    pub(crate) fn unify_veth_and_eth(&mut self) {
        for iface in self.kernel_ifaces.values_mut() {
            if let Interface::Ethernet(iface) = iface {
                iface.base.iface_type = InterfaceType::Ethernet;
            }
        }
        for nt in self.insert_order.as_mut_slice() {
            if nt.1 == InterfaceType::Veth {
                nt.1 = InterfaceType::Ethernet;
            }
        }
    }

    pub(crate) fn remove_ignored_ifaces(
        &mut self,
        ignored_ifaces: &[(String, InterfaceType)],
    ) {
        for (iface_name, iface_type) in ignored_ifaces {
            self.remove_iface(iface_name.as_str(), iface_type.clone());
        }

        let kernel_iface_names: HashSet<String> = HashSet::from_iter(
            ignored_ifaces
                .iter()
                .filter(|(_, t)| !t.is_userspace())
                .map(|(n, _)| n.to_string()),
        );

        // Remove ignored_iface from port list or veth peer also
        for iface in self
            .kernel_ifaces
            .values_mut()
            .chain(self.user_ifaces.values_mut())
            .filter(|i| i.is_controller())
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
                        }
                    }
                }
            }
        }
    }

    // In memory_only mode, absent interface equal to down
    // action.
    pub(crate) fn apply_memory_only_mode(&mut self) {
        for iface in self.iter_mut().filter(|i| i.is_absent()) {
            iface.base_iface_mut().state = InterfaceState::Down;
        }
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
                        let mut new_iface = cur_iface.clone_name_type_only();
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
                                "Failed to find unknown type interface {iface_name} \
                                in current state"
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

    // If any desired interface has `identifier: mac-address`:
    //  * Resolve interface.name to MAC address match interface name.
    //  * Store interface.name to interface.profile_name.
    fn resolve_mac_identifider_in_desired(
        &mut self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        let mut changed_ifaces: Vec<Interface> = Vec::new();
        for iface in self.iter().filter(|i| {
            i.base_iface().identifier == InterfaceIdentifier::MacAddress
                && i.base_iface().profile_name.is_none()
        }) {
            let mac_address = match iface.base_iface().mac_address.as_deref() {
                Some(m) => m.to_ascii_uppercase(),
                None => {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Desired interface {} has \
                            `identifier: mac-address` but not MAC address \
                            defined",
                            iface.name()
                        ),
                    ));
                }
            };
            let mut has_match = false;
            for cur_iface in current.kernel_ifaces.values() {
                if cur_iface.base_iface().mac_address.as_deref()
                    == Some(&mac_address)
                {
                    let mut new_iface = if iface.iface_type()
                        == InterfaceType::Unknown
                    {
                        let mut new_iface_value = serde_json::to_value(iface)?;
                        if let Some(obj) = new_iface_value.as_object_mut() {
                            obj.insert(
                                "type".to_string(),
                                serde_json::Value::String(
                                    cur_iface.iface_type().to_string(),
                                ),
                            );
                        }
                        Interface::deserialize(new_iface_value)?
                    } else {
                        iface.clone()
                    };
                    new_iface.base_iface_mut().profile_name =
                        Some(iface.base_iface().name.clone());
                    new_iface.base_iface_mut().name =
                        cur_iface.name().to_string();
                    changed_ifaces.push(new_iface);
                    has_match = true;
                    break;
                }
            }
            if !has_match {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Desired interface {} has `identifier: mac-address` \
                    with MAC address {mac_address}, but no interface is \
                    holding that MAC address",
                        iface.name()
                    ),
                ));
            }
        }
        for changed_iface in changed_ifaces {
            if let Some(profile_name) =
                changed_iface.base_iface().profile_name.as_deref()
            {
                self.kernel_ifaces.remove(profile_name);
            }
            self.push(changed_iface);
        }
        Ok(())
    }

    // If any desired interface is referring to a mac-based current interface:
    //  * Resolve interface.name to MAC address match interface name.
    //  * Store interface.name to interface.profile_name(if not define).
    fn resolve_mac_identifider_in_current(
        &mut self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        let mut changed_ifaces: Vec<Interface> = Vec::new();
        for cur_iface in current.kernel_ifaces.values().filter(|i| {
            i.base_iface().identifier == InterfaceIdentifier::MacAddress
        }) {
            if let Some(profile_name) =
                cur_iface.base_iface().profile_name.as_ref()
            {
                if let Some(des_iface) = self.kernel_ifaces.get(profile_name) {
                    let mut new_iface =
                        if des_iface.iface_type() == InterfaceType::Unknown {
                            let mut new_iface_value =
                                serde_json::to_value(des_iface)?;
                            if let Some(obj) = new_iface_value.as_object_mut() {
                                obj.insert(
                                    "type".to_string(),
                                    serde_json::Value::String(
                                        cur_iface.iface_type().to_string(),
                                    ),
                                );
                            }
                            Interface::deserialize(new_iface_value)?
                        } else {
                            des_iface.clone()
                        };

                    new_iface.base_iface_mut().identifier =
                        InterfaceIdentifier::MacAddress;
                    new_iface.base_iface_mut().mac_address =
                        cur_iface.base_iface().mac_address.clone();
                    new_iface.base_iface_mut().name =
                        cur_iface.name().to_string();
                    new_iface.base_iface_mut().profile_name =
                        Some(profile_name.to_string());
                    changed_ifaces.push(new_iface);
                }
            }
        }
        for changed_iface in changed_ifaces {
            if let Some(profile_name) =
                changed_iface.base_iface().profile_name.as_deref()
            {
                self.kernel_ifaces.remove(profile_name);
            }
            self.push(changed_iface);
        }
        Ok(())
    }

    pub(crate) fn get_iface_mut<'a>(
        &'a mut self,
        iface_name: &str,
        iface_type: InterfaceType,
    ) -> Option<&'a mut Interface> {
        if iface_type.is_userspace() {
            self.user_ifaces
                .get_mut(&(iface_name.to_string(), iface_type))
        } else {
            self.kernel_ifaces.get_mut(&iface_name.to_string())
        }
    }

    pub(crate) fn set_missing_port_to_eth(&mut self) {
        let mut iface_names_to_add = Vec::new();
        for iface in
            self.kernel_ifaces.values().chain(self.user_ifaces.values())
        {
            if let Some(ports) = iface.ports() {
                for port in ports {
                    if !self.kernel_ifaces.contains_key(port) {
                        iface_names_to_add.push(port.to_string());
                    }
                }
            }
        }
        for iface_name in iface_names_to_add {
            let mut iface = EthernetInterface::default();
            iface.base.name = iface_name.clone();
            log::warn!("Assuming undefined port {} as ethernet", iface_name);
            self.kernel_ifaces
                .insert(iface_name, Interface::Ethernet(iface));
        }
    }

    pub(crate) fn set_unknown_iface_to_eth(
        &mut self,
    ) -> Result<(), NmstateError> {
        let mut new_ifaces = Vec::new();
        for iface in self.kernel_ifaces.values_mut() {
            if let Interface::Unknown(iface) = iface {
                log::warn!(
                    "Setting unknown type interface {} to ethernet",
                    iface.base.name.as_str()
                );
                let iface_value = match serde_json::to_value(&iface) {
                    Ok(mut v) => {
                        if let Some(v) = v.as_object_mut() {
                            v.insert(
                                "type".to_string(),
                                serde_json::Value::String(
                                    "ethernet".to_string(),
                                ),
                            );
                        }
                        v
                    }
                    Err(e) => {
                        return Err(NmstateError::new(
                            ErrorKind::Bug,
                            format!(
                                "BUG: Failed to convert {iface:?} to serde_json \
                                value: {e}"
                            ),
                        ));
                    }
                };
                match EthernetInterface::deserialize(&iface_value) {
                    Ok(i) => new_ifaces.push(i),
                    Err(e) => {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Invalid property for ethernet interface: {e}"
                            ),
                        ));
                    }
                }
            }
        }
        for iface in new_ifaces {
            self.kernel_ifaces.insert(
                iface.base.name.to_string(),
                Interface::Ethernet(iface),
            );
        }
        Ok(())
    }
}

fn is_opt_str_empty(opt_string: &Option<String>) -> bool {
    if let Some(s) = opt_string {
        s.is_empty()
    } else {
        true
    }
}

// When merging desire interface with current, we perform actions in the order
// of:
//  * Action might alter the results of follow-up actions:
//    `MergedInterface.pre_inter_ifaces_process()` # For example, empty OVS
//    bridge will get a auto created ovs internal # interface.
//  * Actions required the knowledge of multiple interfaces:
//    `MergedInterfaces.process()` # For example, mark changed port as changed
//    and complex controller/port # validation
//  * Actions required both the knowledge of desired and current of single
//    interface: `MergedInterface.post_inter_ifaces_process()`. # Validations
//    after controller/port information are ready.
//  * Actions self-contained of each `Interface` -- `Interface.sanitize()`. #
//    Self clean up.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MergedInterfaces {
    pub(crate) kernel_ifaces: HashMap<String, MergedInterface>,
    pub(crate) user_ifaces: HashMap<(String, InterfaceType), MergedInterface>,
    pub(crate) insert_order: Vec<(String, InterfaceType)>,
    pub(crate) ignored_ifaces: Vec<(String, InterfaceType)>,
    pub(crate) memory_only: bool,
    pub(crate) gen_conf_mode: bool,
}

impl MergedInterfaces {
    // The gen_conf mode will do extra stuff:
    //  * Set unknown interface as ethernet instead of raising failure.
    //  * Set unknown port as ethernet instead of raising failure.
    pub(crate) fn new(
        mut desired: Interfaces,
        mut current: Interfaces,
        gen_conf_mode: bool,
        memory_only: bool,
    ) -> Result<Self, NmstateError> {
        let mut merged_kernel_ifaces: HashMap<String, MergedInterface> =
            HashMap::new();
        let mut merged_user_ifaces: HashMap<
            (String, InterfaceType),
            MergedInterface,
        > = HashMap::new();

        if gen_conf_mode {
            desired.set_unknown_iface_to_eth()?;
            desired.set_missing_port_to_eth();
        } else {
            desired.resolve_sriov_reference(&current)?;
            desired.resolve_mac_identifider_in_current(&current)?;
            desired.resolve_unknown_ifaces(&current)?;
            desired.resolve_mac_identifider_in_desired(&current)?;
        }

        desired.auto_managed_controller_ports(&current);

        let ignored_ifaces = get_ignored_ifaces(&desired, &current);
        desired.pre_ignore_check(&current, ignored_ifaces.as_slice())?;

        if memory_only {
            desired.apply_memory_only_mode();
        }

        for (iface_name, iface_type) in ignored_ifaces.as_slice() {
            log::info!("Ignoring interface {} type {}", iface_name, iface_type);
        }

        desired.remove_ignored_ifaces(ignored_ifaces.as_slice());
        current.remove_ignored_ifaces(ignored_ifaces.as_slice());

        desired.unify_veth_and_eth();
        current.unify_veth_and_eth();

        for (iface_name, des_iface) in desired
            .kernel_ifaces
            .drain()
            .chain(desired.user_ifaces.drain().map(|((n, _), i)| (n, i)))
        {
            let merged_iface = MergedInterface::new(
                Some(des_iface.clone()),
                current.remove_iface(&iface_name, des_iface.iface_type()),
            )?;
            if merged_iface.merged.is_userspace() {
                merged_user_ifaces.insert(
                    (
                        merged_iface.merged.name().to_string(),
                        merged_iface.merged.iface_type(),
                    ),
                    merged_iface,
                );
            } else {
                merged_kernel_ifaces.insert(
                    merged_iface.merged.name().to_string(),
                    merged_iface,
                );
            }
        }

        // Interfaces only exists in current
        for cur_iface in current
            .kernel_ifaces
            .drain()
            .chain(current.user_ifaces.drain().map(|((n, _), i)| (n, i)))
            .map(|(_, i)| i)
        {
            let merged_iface = MergedInterface::new(None, Some(cur_iface))?;
            if merged_iface.merged.is_userspace() {
                merged_user_ifaces.insert(
                    (
                        merged_iface.merged.name().to_string(),
                        merged_iface.merged.iface_type(),
                    ),
                    merged_iface,
                );
            } else {
                merged_kernel_ifaces.insert(
                    merged_iface.merged.name().to_string(),
                    merged_iface,
                );
            }
        }
        let mut ret = Self {
            kernel_ifaces: merged_kernel_ifaces,
            user_ifaces: merged_user_ifaces,
            insert_order: desired.insert_order,
            ignored_ifaces,
            memory_only,
            gen_conf_mode,
        };

        ret.process()?;

        Ok(ret)
    }

    pub(crate) fn get_iface<'a>(
        &'a self,
        iface_name: &str,
        iface_type: InterfaceType,
    ) -> Option<&'a MergedInterface> {
        if iface_type == InterfaceType::Unknown {
            self.kernel_ifaces.get(&iface_name.to_string()).or_else(|| {
                self.user_ifaces
                    .values()
                    .find(|&iface| iface.merged.name() == iface_name)
            })
        } else if iface_type.is_userspace() {
            self.user_ifaces.get(&(iface_name.to_string(), iface_type))
        } else {
            self.kernel_ifaces.get(&iface_name.to_string())
        }
    }

    pub(crate) fn iter(&self) -> impl Iterator<Item = &MergedInterface> {
        self.user_ifaces.values().chain(self.kernel_ifaces.values())
    }

    pub(crate) fn iter_mut(
        &mut self,
    ) -> impl Iterator<Item = &mut MergedInterface> {
        self.user_ifaces
            .values_mut()
            .chain(self.kernel_ifaces.values_mut())
    }

    // Contains all the smart modifications, validations among interfaces
    fn process(&mut self) -> Result<(), NmstateError> {
        self.process_allow_extra_ovs_patch_ports_for_apply();
        self.apply_copy_mac_from()?;
        self.validate_controller_and_port_list_confliction()?;
        self.handle_changed_ports()?;
        self.resolve_port_iface_controller_type()?;
        self._set_up_priority()?;
        self.check_overbook_ports()?;
        self.check_infiniband_as_ports()?;
        self.mark_orphan_interface_as_absent()?;
        self.process_veth_peer_changes()?;
        for iface in self
            .kernel_ifaces
            .values_mut()
            .chain(self.user_ifaces.values_mut())
            .filter(|i| i.is_changed())
        {
            iface.post_inter_ifaces_process()?;
        }
        Ok(())
    }

    fn _set_up_priority(&mut self) -> Result<(), NmstateError> {
        for _ in 0..INTERFACES_SET_PRIORITY_MAX_RETRY {
            if self.set_ifaces_up_priority() {
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

    fn apply_copy_mac_from(&mut self) -> Result<(), NmstateError> {
        let mut pending_changes: HashMap<String, String> = HashMap::new();
        for (iface_name, merged_iface) in self.kernel_ifaces.iter() {
            if !merged_iface.is_desired()
                || !COPY_MAC_ALLOWED_IFACE_TYPES
                    .contains(&merged_iface.merged.iface_type())
            {
                continue;
            }
            if let Some(src_iface_name) =
                &merged_iface.merged.base_iface().copy_mac_from
            {
                if let Some(src_iface) =
                    self.kernel_ifaces.get(src_iface_name).map(|i| &i.merged)
                {
                    if !is_opt_str_empty(
                        &src_iface.base_iface().permanent_mac_address,
                    ) {
                        if let Some(mac) = src_iface
                            .base_iface()
                            .permanent_mac_address
                            .as_ref()
                        {
                            pending_changes.insert(
                                iface_name.to_string(),
                                mac.to_string(),
                            );
                        }
                    } else if !is_opt_str_empty(
                        &src_iface.base_iface().mac_address,
                    ) {
                        if let Some(mac) =
                            src_iface.base_iface().mac_address.as_ref()
                        {
                            pending_changes.insert(
                                iface_name.to_string(),
                                mac.to_string(),
                            );
                        }
                    } else {
                        let e = NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Failed to find mac address of \
                                interface {src_iface_name} \
                                for copy-mac-from of iface {iface_name}"
                            ),
                        );
                        log::error!("{}", e);
                        return Err(e);
                    }
                } else {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Failed to find interface {src_iface_name} for \
                            copy-mac-from of iface {iface_name}"
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
        }
        for (iface_name, mac) in pending_changes.drain() {
            if let Some(iface) = self.kernel_ifaces.get_mut(&iface_name) {
                iface.set_copy_from_mac(mac);
            }
        }
        Ok(())
    }

    // Unlike orphan check in `apply_ctrller_change()`, this function is for
    // orphan interface without controller.
    fn mark_orphan_interface_as_absent(&mut self) -> Result<(), NmstateError> {
        let gone_ifaces: Vec<String> = self
            .kernel_ifaces
            .values()
            .filter(|i| {
                // User can still have VLAN over ethernet even ethernet is
                // marked as absent.
                // For veth, it is hard for us to know whether absent action
                // delete it not, hence treat it as ethernet.
                i.is_changed()
                    && i.merged.is_absent()
                    && i.merged.iface_type() != InterfaceType::Ethernet
            })
            .map(|i| i.merged.name().to_string())
            .collect();

        // OvsInterface is already checked by `apply_ctrller_change()`.
        for iface in self.kernel_ifaces.values_mut().filter(|i| {
            i.merged.is_up()
                && i.merged.iface_type() != InterfaceType::OvsInterface
        }) {
            if let Some(parent) = iface.merged.parent() {
                if gone_ifaces.contains(&parent.to_string()) {
                    if iface.is_desired() && iface.merged.is_up() {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Interface {} cannot be in up state \
                                as its parent {parent} has been marked \
                                as absent",
                                iface.merged.name(),
                            ),
                        ));
                    }
                    log::info!(
                        "Marking interface {} as absent as its \
                        parent {} is so",
                        iface.merged.name(),
                        parent
                    );
                    iface.mark_as_absent();
                }
            }
        }
        Ok(())
    }
}

// Special cases:
//  * Inherit the ignore state from current if desire not mentioned in interface
//    section
//  * Return Vec<> has all InterfaceType::Veth is converted to
//    InterfaceType::Ethernet
fn get_ignored_ifaces(
    desired: &Interfaces,
    current: &Interfaces,
) -> Vec<(String, InterfaceType)> {
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

    let mut ignored_ifaces: Vec<(String, InterfaceType)> =
        ignored_user_ifaces.drain().collect();

    for iface_name in ignored_kernel_ifaces {
        if let Some(iface) = desired
            .get_iface(&iface_name, InterfaceType::Unknown)
            .or_else(|| current.get_iface(&iface_name, InterfaceType::Unknown))
        {
            let iface_type = match iface.iface_type() {
                InterfaceType::Veth => InterfaceType::Ethernet,
                t => t,
            };
            ignored_ifaces.push((iface_name, iface_type));
        }
    }

    ignored_ifaces
}
