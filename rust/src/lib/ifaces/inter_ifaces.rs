use std::collections::{HashMap, HashSet};
use std::iter::FromIterator;

use log::{debug, error, info};
use serde::{
    ser::SerializeSeq, Deserialize, Deserializer, Serialize, Serializer,
};

use crate::{
    ifaces::ethernet::handle_veth_peer_changes,
    ifaces::inter_ifaces_controller::{
        check_infiniband_as_ports, check_overbook_ports,
        find_unknown_type_port, handle_changed_ports,
        preserve_ctrl_cfg_if_unchanged, set_ifaces_up_priority,
        set_missing_port_to_eth, validate_new_ovs_iface_has_controller,
    },
    ifaces::sriov::check_sriov_capability,
    ip::{include_current_ip_address_if_dhcp_on_to_off, merge_ip_stack},
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
        ifaces.sort_unstable_by_key(|iface| iface.name());
        // Use sort_by_key() instead of unstable one, do we can alphabet
        // activation order which is required to simulate the OS boot-up.
        ifaces.sort_by_key(|iface| iface.base_iface().up_priority);

        ifaces
    }

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

    fn get_iface_mut<'a, 'b>(
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

    pub fn update(&mut self, other: &Self) {
        let mut new_ifaces: Vec<&Interface> = Vec::new();
        let other_ifaces = other.to_vec();
        for other_iface in &other_ifaces {
            match self
                .get_iface_mut(other_iface.name(), other_iface.iface_type())
            {
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
        for new_iface in new_ifaces {
            self.push(new_iface.clone());
        }
    }

    pub(crate) fn verify(&self, cur_ifaces: &Self) -> Result<(), NmstateError> {
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
        // When user is not mentioning `enabled` property of ipv4/ipv6 stack
        // in desire state, nmstate should merge it from current.
        merge_ip_stack(&mut self_clone, &cur_clone);

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
                // Do not verify physical interface with state:down
                if !iface.is_down() {
                    iface.verify(cur_iface)?;
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
        handle_changed_ports(self, current)?;
        preserve_ctrl_cfg_if_unchanged(self, current);
        self.set_up_priority()?;
        check_overbook_ports(self, current)?;
        check_infiniband_as_ports(self, current)?;
        if !current.kernel_ifaces.is_empty() {
            check_sriov_capability(self)?;
        }
        // When user is not mentioning `enabled` property of ipv4/ipv6 stack
        // in desire state, nmstate should merge it from current.
        // As this requires the extra checks before merging IP stack from
        // current, this should be done at top level instead of plugin.
        merge_ip_stack(self, current);

        for iface in self.to_vec() {
            if iface.is_absent() {
                for del_iface in gen_ifaces_to_del(iface, current) {
                    del_ifaces.push(del_iface);
                }
            } else {
                if iface.is_up() {
                    iface.validate(
                        current.get_iface(iface.name(), iface.iface_type()),
                    )?;
                }
                match current.get_iface(iface.name(), iface.iface_type()) {
                    Some(cur_iface) => {
                        let mut chg_iface = iface.clone();
                        if cur_iface.iface_type() == InterfaceType::Unknown {
                            chg_iface.set_iface_type(cur_iface.iface_type());
                        }
                        chg_iface.pre_edit_cleanup()?;
                        info!(
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
                        new_iface.pre_edit_cleanup()?;
                        info!(
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

        // Normally, we expect backend to preserve configuration which not
        // mentioned in desire, but when DHCP switch from ON to OFF, the design
        // of nmstate is expecting dynamic IP address goes static. This should
        // be done by top level code.
        include_current_ip_address_if_dhcp_on_to_off(&mut chg_ifaces, current);
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

    pub(crate) fn has_sriov_enabled(&self) -> bool {
        self.kernel_ifaces.values().any(|i| {
            if let Interface::Ethernet(eth_iface) = i {
                eth_iface.sriov_is_enabled()
            } else {
                false
            }
        })
    }

    pub(crate) fn set_unknown_iface_to_eth(&mut self) {
        for iface in self.kernel_ifaces.values_mut() {
            if iface.iface_type() == InterfaceType::Unknown {
                log::warn!(
                    "Setting unknown type interface {} to ethernet",
                    iface.name()
                );
                iface.base_iface_mut().iface_type = InterfaceType::Ethernet;
            }
        }
    }

    pub(crate) fn set_missing_port_to_eth(&mut self) {
        set_missing_port_to_eth(self);
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
                        error!("{}", e);
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
                        error!("{}", e);
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
        error!("{}", e);
        Err(e)
    } else if cur_iface.is_up() {
        // Real hardware should be marked as down by absent action
        let e = NmstateError::new(
            ErrorKind::VerificationError,
            format!(
                "Absent interface {}/{} still found as \
                state up: {:?}",
                des_iface.name(),
                des_iface.iface_type(),
                cur_iface
            ),
        );
        error!("{}", e);
        Err(e)
    } else {
        Ok(())
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
            info!(
                "Deleting interface {}/{}",
                tmp_iface.name(),
                tmp_iface.iface_type()
            );
            del_ifaces.push(tmp_iface);
        }
    }
    if del_ifaces.is_empty() {
        info!(
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

pub(crate) fn purge_userspace_ignored_ifaces(state: &mut Interfaces) {
    state.user_ifaces.retain(|_, iface| !iface.is_ignore())
}
