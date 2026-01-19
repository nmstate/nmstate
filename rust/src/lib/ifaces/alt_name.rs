// SPDX-License-Identifier: Apache-2.0

use std::collections::{HashMap, HashSet};

use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, ErrorKind, InterfaceIdentifier, Interfaces,
    MergedInterfaces, NmstateError,
};

#[derive(
    Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize,
)]
#[non_exhaustive]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub enum AltNameState {
    Absent,
}

#[derive(
    Debug,
    Clone,
    PartialEq,
    Eq,
    Default,
    Hash,
    PartialOrd,
    Ord,
    Serialize,
    Deserialize,
)]
#[non_exhaustive]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct AltNameEntry {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Set to `state: absent` will delete specified alternative name.
    pub state: Option<AltNameState>,
}

impl AltNameEntry {
    pub fn is_absent(&self) -> bool {
        self.state == Some(AltNameState::Absent)
    }
}

impl BaseInterface {
    // * Sort alt names
    // * Alt name cannot be the same as interface name
    pub(crate) fn sanitize_alt_names(&mut self) -> Result<(), NmstateError> {
        if let Some(alt_names) = self.alt_names.as_mut() {
            for alt_name in alt_names.iter() {
                if !alt_name.is_absent() && alt_name.name == self.name {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Alternative name cannot be the same with \
                             interface name {}",
                            alt_name.name
                        ),
                    ));
                }
            }
            alt_names.sort_unstable();
        }
        Ok(())
    }
}

impl MergedInterfaces {
    pub(crate) fn validate_alt_names(&self) -> Result<(), NmstateError> {
        // HashMap<alt_name, iface_name>
        let mut all_alt_names: HashMap<&str, &str> = HashMap::new();

        let all_iface_names: HashSet<&str> =
            self.kernel_ifaces.keys().map(|s| s.as_str()).collect();

        for cur_iface in
            self.kernel_ifaces.values().filter_map(|merged_iface| {
                merged_iface.current.as_ref().map(|i| i.base_iface())
            })
        {
            if let Some(alt_names) = cur_iface.alt_names.as_ref() {
                for alt_name in alt_names {
                    all_alt_names.insert(
                        alt_name.name.as_str(),
                        cur_iface.name.as_str(),
                    );
                }
            }
        }
        for des_iface in
            self.kernel_ifaces.values().filter_map(|merged_iface| {
                merged_iface.for_apply.as_ref().map(|i| i.base_iface())
            })
        {
            if let Some(alt_names) = des_iface.alt_names.as_ref() {
                for alt_name in alt_names {
                    if alt_name.is_absent() {
                        all_alt_names.remove(alt_name.name.as_str());
                    } else if let Some(other_iface_name) =
                        all_alt_names.get(alt_name.name.as_str())
                    {
                        if other_iface_name != &des_iface.name {
                            return Err(NmstateError::new(
                                ErrorKind::InvalidArgument,
                                format!(
                                    "Desired alt-name {} for interface {} is \
                                     already used by interface {}",
                                    alt_name.name,
                                    des_iface.name,
                                    other_iface_name
                                ),
                            ));
                        };
                    } else if all_iface_names.contains(&alt_name.name.as_str())
                    {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Desired alt-name {} for interface {} is \
                                 already an interface name of other NIC",
                                alt_name.name, des_iface.name,
                            ),
                        ));
                    } else {
                        all_alt_names.insert(
                            alt_name.name.as_str(),
                            des_iface.name.as_str(),
                        );
                    }
                }
            }
        }
        Ok(())
    }
}

impl Interfaces {
    pub(crate) fn resolve_alt_name_reference_in_desired(
        &mut self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        let mut alt_name_to_kernel_name: HashMap<&str, &str> = HashMap::new();
        // Pending changes: HashMap<alt_name, resolved_kernel_name>
        let mut pending_changes: HashMap<String, String> = HashMap::new();

        for cur_iface in current.kernel_ifaces.values() {
            if let Some(alt_names) = cur_iface.base_iface().alt_names.as_ref() {
                for alt_name in alt_names {
                    alt_name_to_kernel_name
                        .insert(alt_name.name.as_str(), cur_iface.name());
                }
            }
        }

        for des_iface in self.kernel_ifaces.values() {
            // Skip on desire interface which is not `identifier: Some(name)` or
            // `identifier: None`
            if !matches!(
                des_iface.base_iface().identifier.as_ref(),
                None | Some(InterfaceIdentifier::Name)
            ) {
                continue;
            }
            if !current.kernel_ifaces.contains_key(des_iface.name())
                && let Some(kernel_name) =
                    alt_name_to_kernel_name.get(des_iface.name())
            {
                // It is OK to have both alt-name and kernel interface marked
                // as absent
                if let Some(exist_kernel_iface) =
                    self.kernel_ifaces.get(*kernel_name)
                    && !(exist_kernel_iface.is_absent()
                        && des_iface.is_absent())
                {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Interface {}/({}) is alt-name of kernel \
                             interface {kernel_name}, but desired state also \
                             contains a conflicting configuration for kernel \
                             interface {kernel_name}, please merge them",
                            des_iface.name(),
                            des_iface.iface_type(),
                        ),
                    ));
                }
                pending_changes.insert(
                    des_iface.name().to_string(),
                    kernel_name.to_string(),
                );
            }
        }

        for (alt_name, kernel_name) in pending_changes.drain() {
            if let Some(mut des_iface) = self.kernel_ifaces.remove(&alt_name) {
                // Move interface name to profile name if profile name not
                // defined in desire or current state.
                if des_iface.is_up()
                    && des_iface.base_iface().profile_name.is_none()
                    && current
                        .kernel_ifaces
                        .get(&kernel_name)
                        .and_then(|i| i.base_iface().profile_name.as_ref())
                        .is_none()
                {
                    des_iface.base_iface_mut().profile_name =
                        Some(des_iface.base_iface().name.to_string());
                }
                des_iface.base_iface_mut().name = kernel_name;
                self.push(des_iface);
            }
        }
        Ok(())
    }
}
