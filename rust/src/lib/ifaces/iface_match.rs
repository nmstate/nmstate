// SPDX-License-Identifier: Apache-2.0

use std::collections::{HashMap, HashSet};

use serde::{Deserialize, Serialize};

use crate::{
    ErrorKind, InterfaceIdentifier, InterfaceType, Interfaces, MergedInterface,
    NmstateError,
};

#[derive(Debug, Clone, PartialEq, Eq, Default)]
#[non_exhaustive]
pub(crate) struct IfaceMatchCache {
    // Holding interface name as key.
    names: HashMap<String, InterfaceType>,
    // Holding MAC address as key, Vec<(iface_name, iface_type)> as value.
    // It is OK to overlap in current state, as long as the desired state is
    // not ambiguous on port referring.
    permanent: HashMap<String, Vec<(String, InterfaceType)>>,
    active: HashMap<String, Vec<(String, InterfaceType)>>,
}

impl IfaceMatchCache {
    pub(crate) fn new(desired: &Interfaces, current: &Interfaces) -> Self {
        let mut permanent: HashMap<String, Vec<(String, InterfaceType)>> =
            HashMap::new();
        let mut active: HashMap<String, Vec<(String, InterfaceType)>> =
            HashMap::new();
        let mut names: HashMap<String, InterfaceType> = HashMap::new();
        let absent_iface_names: HashSet<String> = HashSet::from_iter(
            desired
                .kernel_ifaces
                .values()
                .filter(|i| i.is_absent())
                .map(|i| i.name().to_string()),
        );

        for iface in current
            .kernel_ifaces
            .values()
            .chain(desired.kernel_ifaces.values())
            .filter(|i| i.iface_type() != InterfaceType::Unknown)
        {
            names.insert(iface.name().to_string(), iface.iface_type());
        }

        for use_permanent in [true, false] {
            for (iface, mac) in current
                .kernel_ifaces
                .values()
                .chain(desired.kernel_ifaces.values())
                .filter_map(|i| {
                    if i.iface_type() == InterfaceType::Loopback {
                        return None;
                    }
                    if absent_iface_names.contains(i.name()) {
                        return None;
                    }
                    let mac_addr = if use_permanent {
                        i.base_iface().permanent_mac_address.as_deref()
                    } else {
                        i.base_iface().mac_address.as_deref()
                    };
                    if let Some(mac) = mac_addr {
                        if !mac.is_empty() && mac != "00:00:00:00:00:00" {
                            return Some((i, mac));
                        }
                    }
                    None
                })
            {
                if use_permanent {
                    permanent.entry(mac.to_uppercase())
                } else {
                    active.entry(mac.to_uppercase())
                }
                .and_modify(|v| {
                    v.push((iface.name().to_string(), iface.iface_type()))
                })
                .or_insert(vec![(
                    iface.name().to_string(),
                    iface.iface_type(),
                )]);
            }
        }

        Self {
            names,
            permanent,
            active,
        }
    }

    pub(crate) fn search_by_name(&self, name: &str) -> Option<InterfaceType> {
        self.names.get(name).cloned()
    }

    pub(crate) fn search_by_mac(
        &self,
        mac: &str,
    ) -> Option<Vec<(String, InterfaceType)>> {
        let mac = mac.to_uppercase();
        self.permanent
            .get(mac.as_str())
            .or_else(|| self.active.get(mac.as_str()))
            .cloned()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
/// Interface matching rule
/// [InterfaceMatchRule::default()] means remove all interface matching rules
/// and fallback to interface name matching. For example:
/// This section will not merge with current state when applying, you
/// need to define the whole matching rules.
pub struct InterfaceMatchRule {
    /// Matching interface by interface name.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    /// Matching interface by MAC address. Prefer permanent MAC address over
    /// active mac address.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mac_address: Option<String>,
    /// Matching interface by interface type.
    /// Setting as [InterfaceType::Unknown] means any interface type matches.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub iface_type: Option<InterfaceType>,
}

impl std::fmt::Display for InterfaceMatchRule {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut wrote = false;
        if let Some(name) = self.name.as_deref() {
            write!(f, "name:{name}")?;
            wrote = true;
        }
        if let Some(mac) = self.mac_address.as_deref() {
            if wrote {
                write!(f, ",mac-address:{mac}")?;
            } else {
                write!(f, "mac-address:{mac}")?;
            }
            wrote = true;
        }
        if let Some(iface_type) = self.iface_type.as_ref() {
            if wrote {
                write!(f, ",iface-type:{iface_type}")?;
            } else {
                write!(f, "iface-type:{iface_type}")?;
            }
            wrote = true;
        }

        if !wrote {
            write!(f, "none")
        } else {
            Ok(())
        }
    }
}

impl InterfaceMatchRule {
    // Change MAC address to upper case
    // Change veth interface type to ethernet
    pub(crate) fn sanitize(&mut self) {
        self.mac_address = self.mac_address.as_ref().map(|m| m.to_uppercase());
        if let Some(InterfaceType::Veth) = self.iface_type.as_ref() {
            self.iface_type = Some(InterfaceType::Ethernet);
        }
    }

    // Set interface profile to `<controller_name>-port<index>` (e.g. br0-port1)
    // if `porfile_name` not desired.
    // Changed specified interface's identifier according to InterfaceMatchRule
    // Raise error when any of these conditions matches:
    //  * Desired `identifier: name` but match rule is not name only.
    //  * Desired `identifier: mac-address` but match rule is name only.
    //  * Desired mac address different from match rule MAC address. Means user
    //    is changing MAC address and matching by mac address at the same time.
    pub(crate) fn apply_port_match_to_iface(
        &self,
        iface: &mut MergedInterface,
        port_index: usize,
    ) -> Result<(), NmstateError> {
        if let Some(desired_iface) = iface.desired.as_ref() {
            if (!self.is_name_match_only())
                && desired_iface.base_iface().identifier.as_ref()
                    == Some(&InterfaceIdentifier::Name)
            {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Interface {}({}) is desired to use \
                        'identifier: name' but its controller {} \
                        is requesting port match by other rule: {}",
                        desired_iface.name(),
                        desired_iface.iface_type(),
                        desired_iface
                            .base_iface()
                            .controller
                            .as_deref()
                            .unwrap_or(""),
                        self
                    ),
                ));
            }
            if (self.is_name_match_only())
                && desired_iface.base_iface().identifier.as_ref()
                    == Some(&InterfaceIdentifier::MacAddress)
            {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Interface {}({}) is desired to use \
                        'identifier: mac-address' but its controller {} \
                        is requesting port match by name",
                        desired_iface.name(),
                        desired_iface.iface_type(),
                        desired_iface
                            .base_iface()
                            .controller
                            .as_deref()
                            .unwrap_or(""),
                    ),
                ));
            }
            if let (Some(des_mac), Some(rule_mac)) = (
                desired_iface.base_iface().mac_address.as_deref(),
                self.mac_address.as_deref(),
            ) {
                if des_mac != rule_mac {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Interface {}({}) is desired to change MAC address \
                            to {}, but its controller {} \
                            is requesting port match by its MAC address {}",
                            desired_iface.name(),
                            desired_iface.iface_type(),
                            des_mac,
                            desired_iface
                                .base_iface()
                                .controller
                                .as_deref()
                                .unwrap_or(""),
                            rule_mac
                        ),
                    ));
                }
            }
        }
        if let Some(for_apply) = iface.for_apply.as_mut() {
            if self.is_name_match_only() {
                for_apply.base_iface_mut().identifier =
                    Some(InterfaceIdentifier::Name);
            } else {
                for_apply.base_iface_mut().identifier =
                    Some(InterfaceIdentifier::MacAddress);
                for_apply.base_iface_mut().mac_address =
                    self.mac_address.clone();
                log::info!(
                    "Interface {}/{} is set to \
                    `identifier: mac-address` with `mac-address: {}` \
                    per its controller {} requested",
                    for_apply.name(),
                    for_apply.iface_type(),
                    for_apply.base_iface().mac_address.as_deref().unwrap_or(""),
                    for_apply.base_iface().controller.as_deref().unwrap_or("")
                );

                if for_apply.base_iface().profile_name.is_none() {
                    if let Some(controller_name) =
                        for_apply.base_iface().controller.clone()
                    {
                        for_apply.base_iface_mut().profile_name =
                            Some(format!(
                                "{}-port{}",
                                controller_name,
                                port_index + 1
                            ));
                    }
                }
            }
        }
        Ok(())
    }

    pub(crate) fn is_name_match_only(&self) -> bool {
        self == &Self::default()
            || (self.mac_address.is_none() && self.iface_type.is_none())
    }

    /// Will return [NmstateError] with [ErrorKind::InvalidArgument] when
    /// multiple interface can be matched by specified match rule.
    pub(crate) fn resolve(
        &self,
        cache: &IfaceMatchCache,
    ) -> Result<String, NmstateError> {
        let mut matched_ifaces: HashSet<(String, InterfaceType)> =
            HashSet::new();
        if let Some(name) = self.name.as_deref() {
            match cache.search_by_name(name) {
                Some(iface_type) => {
                    matched_ifaces.insert((name.to_string(), iface_type));
                }
                None => {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!("Failed to find interface holding name {name}"),
                    ))
                }
            }
        }

        if let Some(mac) = self.mac_address.as_deref() {
            if let Some(cur_matched) = cache.search_by_mac(mac) {
                let cur_matched =
                    HashSet::from_iter(cur_matched.iter().cloned());
                if matched_ifaces.is_empty() {
                    matched_ifaces = cur_matched;
                } else {
                    matched_ifaces = cur_matched
                        .intersection(&matched_ifaces)
                        .cloned()
                        .collect();
                }
            } else {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Failed to find interface with MAC address \
                        {mac}"
                    ),
                ));
            }
        }

        if let Some(iface_type) = self.iface_type.as_ref() {
            if iface_type != &InterfaceType::Unknown {
                if self.name.is_none() && self.mac_address.is_none() {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Cannot match interface using interface type only: 
                            {iface_type}"
                        ),
                    ));
                }
                matched_ifaces
                    .retain(|(_, cur_iface_type)| iface_type == cur_iface_type);
            }
        }

        match matched_ifaces.len() {
            len if len > 1 => {
                let match_iface_strs: Vec<String> = matched_ifaces
                    .iter()
                    .map(|(name, iface_type)| format!("{name}/{iface_type}"))
                    .collect();
                Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Found {len} interfaces matching {self} rule: {}",
                        match_iface_strs.join(", ")
                    ),
                ))
            }
            1 => {
                if let Some((name, _)) = matched_ifaces.drain().next() {
                    Ok(name)
                } else {
                    unreachable!(
                        "There should always a item \
                    in matched_ifaces as we just checked its length is 1"
                    );
                }
            }
            0 => Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!("No interface is matching rule: {self}"),
            )),
            _ => unreachable!(
                "Already matched all conditions for \
                InterfaceMatchRule::resolve()"
            ),
        }
    }
}
