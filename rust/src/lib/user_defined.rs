// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::{ErrorKind, NmstateError};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub enum UserDefinedInterfaceTypeState {
    Absent,
}

/// User defined interface types.
/// Please check [UserDefinedInterface] for example.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct UserDefinedInterfaceType {
    pub name: String,
    /// Setting handler_script to empty string will remove this
    /// [UserDefinedInterfaceType].
    #[serde(skip_serializing_if = "Option::is_none")]
    pub handler_script: Option<String>,
    /// You may remove this user defined interface type by setting
    /// `state: absent`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub state: Option<UserDefinedInterfaceTypeState>,
}

impl UserDefinedInterfaceType {
    pub(crate) fn is_absent(&self) -> bool {
        self.handler_script.as_deref() == Some("")
            || self.state == Some(UserDefinedInterfaceTypeState::Absent)
    }
}

/// User defined global configuration
#[derive(Clone, Debug, Serialize, Deserialize, Default, PartialEq, Eq)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case")]
pub struct UserDefinedData {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub interface_types: Option<Vec<UserDefinedInterfaceType>>,
}

impl UserDefinedData {
    pub fn is_none(&self) -> bool {
        self.interface_types.is_none()
    }

    pub(crate) fn is_purge(&self) -> bool {
        match self.interface_types.as_deref() {
            None => false,
            Some(t) => t.is_empty(),
        }
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MergedUserDefinedData {
    pub(crate) desired: HashMap<String, UserDefinedInterfaceType>,
    merged: HashMap<String, UserDefinedInterfaceType>,
}

impl MergedUserDefinedData {
    pub(crate) fn new(
        desired: &UserDefinedData,
        current: &UserDefinedData,
    ) -> Result<Self, NmstateError> {
        let mut desired_map = HashMap::new();
        let mut merged: HashMap<String, UserDefinedInterfaceType> =
            if desired.is_purge() {
                current
                    .interface_types
                    .as_deref()
                    .unwrap_or(&[])
                    .iter()
                    .map(|t| {
                        let mut purge_t = t.clone();
                        purge_t.handler_script = Some(String::new());
                        (t.name.to_string(), purge_t)
                    })
                    .collect()
            } else {
                current
                    .interface_types
                    .as_deref()
                    .unwrap_or(&[])
                    .iter()
                    .map(|t| (t.name.to_string(), t.clone()))
                    .collect()
            };

        if desired.is_purge() {
            desired_map = merged.clone();
        } else if let Some(ts) = desired.interface_types.as_deref() {
            for t in ts {
                if desired_map.contains_key(t.name.as_str()) {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Duplicate definition of user defined \
                            interface type {}",
                            t.name
                        ),
                    ));
                }
                desired_map.insert(t.name.clone(), t.clone());
                merged.insert(t.name.clone(), t.clone());
            }
        }
        Ok(Self {
            desired: desired_map,
            merged,
        })
    }

    pub(crate) fn get_iface_type<'a>(
        &'a self,
        name: &str,
    ) -> Option<&'a UserDefinedInterfaceType> {
        self.merged.get(name)
    }
}
