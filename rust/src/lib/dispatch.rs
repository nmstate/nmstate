// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::{
    ErrorKind, InterfaceType, MergedInterface, MergedInterfaces, NmstateError,
};

#[derive(Debug, Clone, PartialEq, Eq, Default, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct DispatchConfig {
    /// Dispatch bash script content to be invoked after interface activation
    /// finished by network backend. Nmstate will append additional lines
    /// to make sure this script is only invoked for specified interface when
    /// backend interface activation finished.
    /// Setting to empty string will remove the dispatch script
    #[serde(skip_serializing_if = "Option::is_none")]
    pub post_activation: Option<String>,
    /// Dispatch bash script content to be invoked after interface deactivation
    /// finished by network backend. Nmstate will append additional lines
    /// to make sure this script is only invoked for specified interface when
    /// backend interface deactivation finished.
    /// Setting to empty string will remove the dispatch script
    #[serde(skip_serializing_if = "Option::is_none")]
    pub post_deactivation: Option<String>,
    /// Variables passing to interface dispatch scripts including `activation`,
    /// `deactivation`.
    /// The variable can be referred as `$variable_name` in these scripts
    /// and might be converted depend on the implementation of network backend.
    /// Setting to empty string as value will remove the specified variable.
    /// Setting to empty hash map(`Some(HashMap::new())`) will remove all
    /// variables.
    /// The `$name` will be always usable for dispatch scripts holding the
    /// interface name.
    pub variables: Option<HashMap<String, String>>,
    /// Only valid for interface with [InterfaceType::Dispatch]
    /// Serialize and deserialize to/from "type".
    #[serde(skip_serializing_if = "Option::is_none", rename = "type")]
    pub kind: Option<String>,
}

impl MergedInterface {
    pub(crate) fn validate_dispatch(
        &self,
        gen_conf_mode: bool,
    ) -> Result<(), NmstateError> {
        if self
            .for_apply
            .as_ref()
            .map(|f| f.base_iface().dispatch.is_some())
            .unwrap_or_default()
        {
            if gen_conf_mode {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Dispatch script is not supported in gc(gen_conf) mode"
                        .to_string(),
                ));
            } else {
                log::info!(
                    "Dispatch script is not protected by checkpoint, please \
                    backup your original nmstate created dispatch scripts"
                )
            }
        }
        if let Some(iface) = self.for_apply.as_ref() {
            if iface.iface_type() != InterfaceType::Dispatch
                && iface
                    .base_iface()
                    .dispatch
                    .as_ref()
                    .map(|d| d.kind.is_some())
                    == Some(true)
            {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Interface {} with type '{}' is not allowed to \
                            to hold 'dispatch.type' which is dedicated for \
                            interface with type 'dispatch'",
                        iface.name(),
                        iface.iface_type()
                    ),
                ));
            }
        }

        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub enum DispatchInterfaceTypeState {
    Absent,
}

/// Interface type defined by dispatch script.
/// Please check [DispatchInterface] for example.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct DispatchInterfaceType {
    /// When desire state contains dispatch interface type which is already
    /// exist in current state, nmstate will override it instead of adding now.
    /// Hence this `type` should be unique within `dispatch.interfaces`
    /// section.
    /// Deserialize and serialize from/to `type`.
    #[serde(rename = "type")]
    pub kind: String,
    /// Activation dispatch script will be invoked to setup the interface
    /// up on request.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub activation: Option<String>,
    /// Activation dispatch script will be invoked to setup the interface
    /// up on request.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub deactivation: Option<String>,
    /// If dispatch script for this interface type will create kernel
    /// interface, please define a getter script printing its kernel
    /// interface index to STDOUT. For example:
    ///
    /// ```bash
    /// cat /sys/class/net/$name/ifindex
    /// ```
    ///
    /// Setting to None means this interface is user space only interface or
    /// user want nmstate to ignore its kernel interface.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kernel_index_getter: Option<String>,
    /// List of variable name allowed for interface to use.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub allowed_variable_names: Option<Vec<String>>,
    /// Remove this dispatch interface type by setting `state: absent`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub state: Option<DispatchInterfaceTypeState>,
}

impl DispatchInterfaceType {
    pub(crate) fn is_absent(&self) -> bool {
        self.state == Some(DispatchInterfaceTypeState::Absent)
    }
}

/// User defined global configuration
#[derive(Clone, Debug, Serialize, Deserialize, Default, PartialEq, Eq)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct DispatchGlobalConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub interfaces: Option<Vec<DispatchInterfaceType>>,
}

impl DispatchGlobalConfig {
    pub fn is_none(&self) -> bool {
        self.interfaces.is_none()
    }

    pub(crate) fn is_purge(&self) -> bool {
        match self.interfaces.as_deref() {
            None => false,
            Some(t) => t.is_empty(),
        }
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MergedDispatchGlobalConfig {
    pub(crate) desired: HashMap<String, DispatchInterfaceType>,
    current: HashMap<String, DispatchInterfaceType>,
    merged: HashMap<String, DispatchInterfaceType>,
}

impl MergedDispatchGlobalConfig {
    // Besides creating merged configs, also validates:
    //  1. Desired dispatch interface has DispatchInterfaceType defined and not
    //     absent.
    //  2. Absent DispatchInterfaceType has no up/down dispatch interface.
    //  3. Copy current dispatch type to desire if not mentioned
    pub(crate) fn new(
        desired: &DispatchGlobalConfig,
        current: &DispatchGlobalConfig,
        merged_ifaces: &mut MergedInterfaces,
    ) -> Result<Self, NmstateError> {
        let current_map: HashMap<String, DispatchInterfaceType> = current
            .interfaces
            .as_deref()
            .unwrap_or(&[])
            .iter()
            .map(|t| (t.kind.to_string(), t.clone()))
            .collect();

        let desired_map: HashMap<String, DispatchInterfaceType> = if desired
            .is_purge()
        {
            current_map
                .iter()
                .map(|(name, conf)| {
                    let mut purge_conf = conf.clone();
                    purge_conf.state = Some(DispatchInterfaceTypeState::Absent);
                    (name.to_string(), purge_conf)
                })
                .collect()
        } else {
            desired
                .interfaces
                .as_deref()
                .unwrap_or(&[])
                .iter()
                .map(|t| (t.kind.to_string(), t.clone()))
                .collect()
        };

        let merged_map: HashMap<String, DispatchInterfaceType> = if desired
            .is_purge()
        {
            desired_map.clone()
        } else {
            current_map
                .iter()
                .filter(|(name, _)| !desired_map.contains_key(name.as_str()))
                .chain(desired_map.iter())
                .map(|(t, v)| (t.clone(), v.clone()))
                .collect()
        };

        for name in desired_map.keys() {
            if let Some(confs) = desired.interfaces.as_deref() {
                if confs.iter().filter(|c| &c.kind == name).count() >= 2 {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Duplicate dispatch interface type defined for {}",
                            name
                        ),
                    ));
                }
            }
        }

        validate_dispatch_iface_type_exists(&merged_map, merged_ifaces)?;
        validate_dispatch_iface_variables(&merged_map, merged_ifaces)?;
        validate_absent_type(&desired_map, merged_ifaces)?;

        Ok(Self {
            desired: desired_map,
            merged: merged_map,
            current: current_map,
        })
    }

    pub(crate) fn gen_diff(&self) -> DispatchGlobalConfig {
        let mut diff: Vec<DispatchInterfaceType> = Vec::new();
        for (name, des_conf) in self.desired.iter() {
            if let Some(cur_conf) = self.current.get(name.as_str()) {
                if des_conf != cur_conf {
                    diff.push(des_conf.clone());
                }
            }
        }

        if diff.is_empty() {
            DispatchGlobalConfig::default()
        } else {
            DispatchGlobalConfig {
                interfaces: Some(diff),
            }
        }
    }
}

fn validate_dispatch_iface_type_exists(
    merged_dipatch_configs: &HashMap<String, DispatchInterfaceType>,
    merged_ifaces: &mut MergedInterfaces,
) -> Result<(), NmstateError> {
    for iface in merged_ifaces.kernel_ifaces.values_mut().filter(|i| {
        (i.is_desired() | i.is_changed())
            && i.merged.iface_type() == InterfaceType::Dispatch
            && !i.merged.is_absent()
    }) {
        let dispatch_iface_type = if let Some(t) = iface
            .desired
            .as_ref()
            .and_then(|i| i.base_iface().dispatch.as_ref())
            .and_then(|d| d.kind.as_deref())
        {
            t.to_string()
        } else if let Some(t) = iface
            .current
            .as_ref()
            .and_then(|i| i.base_iface().dispatch.as_ref())
            .and_then(|d| d.kind.as_deref())
        {
            t.to_string()
        } else {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "The `dispatch.type` value is undefined for \
                    new dispatch interface {} ",
                    iface.merged.name()
                ),
            ));
        };

        if let Some(dispatch_conf) = iface
            .for_apply
            .as_mut()
            .and_then(|i| i.base_iface_mut().dispatch.as_mut())
        {
            dispatch_conf.kind = Some(dispatch_iface_type.to_string());
        }

        if !merged_dipatch_configs
            .contains_key(&dispatch_iface_type.to_string())
        {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Dispatch interface {} does not have its dispatch  \
                    interface type {} defined in \
                    `dispatch.interfaces` section",
                    iface.merged.name(),
                    dispatch_iface_type
                ),
            ));
        }
        if let Some(dispatch_iface_conf) =
            merged_dipatch_configs.get(&dispatch_iface_type.to_string())
        {
            if dispatch_iface_conf.is_absent() {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Dispatch interface {} is depending on \
                        dispatch interface type {} which is marked \
                        as `absent`",
                        iface.merged.name(),
                        dispatch_iface_type
                    ),
                ));
            }
        }
    }
    Ok(())
}

fn validate_dispatch_iface_variables(
    merged_dipatch_configs: &HashMap<String, DispatchInterfaceType>,
    merged_ifaces: &MergedInterfaces,
) -> Result<(), NmstateError> {
    for base_iface in merged_ifaces
        .kernel_ifaces
        .values()
        .filter_map(|i| i.for_apply.as_ref().map(|i| i.base_iface()))
    {
        let dispatch_iface_type = if let Some(t) =
            base_iface.dispatch.as_ref().and_then(|d| d.kind.as_deref())
        {
            t
        } else {
            continue;
        };
        if let Some(allowed_variable_names) = merged_dipatch_configs
            .get(dispatch_iface_type)
            .and_then(|t| t.allowed_variable_names.as_deref())
        {
            if let Some(invalid_variable) = base_iface
                .dispatch
                .as_ref()
                .and_then(|d| d.variables.as_ref())
                .and_then(|variables| {
                    variables
                        .keys()
                        .find(|v| !allowed_variable_names.contains(v))
                })
            {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "The dispatch interface {} ({}) contains \
                        invalid variable '{}' which is not listed in \
                        `allowed-variable-names` of \
                        `dispatch.interfaces` section of {}",
                        base_iface.name,
                        base_iface.iface_type,
                        invalid_variable,
                        base_iface.iface_type,
                    ),
                ));
            }
        }
    }

    Ok(())
}

fn validate_absent_type(
    desired: &HashMap<String, DispatchInterfaceType>,
    merged_ifaces: &MergedInterfaces,
) -> Result<(), NmstateError> {
    for des_iface_type in desired.values().filter(|t| t.is_absent()) {
        if let Some(iface) = merged_ifaces.kernel_ifaces.values().find(|i| {
            i.merged
                .base_iface()
                .dispatch
                .as_ref()
                .and_then(|d| d.kind.as_deref())
                == Some(des_iface_type.kind.as_str())
                && !i.merged.is_absent()
                && !i.merged.is_ignore()
        }) {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Dispatch interface type {} cannot be removed \
                     because it is referred by interface {} which is \
                     not marked as absent yet",
                    des_iface_type.kind,
                    iface.merged.name()
                ),
            ));
        }
    }

    Ok(())
}
