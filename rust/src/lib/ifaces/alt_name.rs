// SPDX-License-Identifier: Apache-2.0

use std::collections::{HashMap, HashSet};

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, ErrorKind, MergedInterfaces, NmstateError};

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
