// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{
    ErrorKind, Interface, InterfaceType, Interfaces, MergedInterface,
    NmstateError, VlanProtocol,
};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
/// Single Root I/O Virtualization(SRIOV) configuration. The example yaml output
/// of [crate::NetworkState] with SR-IOV enabled ethernet interface would be:
/// ```yml
/// interfaces:
/// - name: ens1f1
///   type: ethernet
///   state: up
///   mac-address: 00:11:22:33:44:55
///   mtu: 1500
///   min-mtu: 68
///   max-mtu: 9702
///   ethernet:
///     sr-iov:
///       total-vfs: 2
///       vfs:
///       - id: 0
///         mac-address: 00:11:22:33:00:ff
///         spoof-check: true
///         trust: false
///         min-tx-rate: 0
///         max-tx-rate: 0
///         vlan-id: 0
///         qos: 0
///       - id: 1
///         mac-address: 00:11:22:33:00:ef
///         spoof-check: true
///         trust: false
///         min-tx-rate: 0
///         max-tx-rate: 0
///         vlan-id: 0
///         qos: 0
/// ```
pub struct SrIovConfig {
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// The number of VFs enabled on PF.
    /// Deserialize and serialize from/to `total-vfs`.
    pub total_vfs: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// VF specific configurations.
    /// * Setting to `Some(Vec::new())` will revert all VF configurations back
    ///   to defaults.
    /// * If not empty, missing [SrIovVfConfig] will use current configuration.
    pub vfs: Option<Vec<SrIovVfConfig>>,
}

impl SrIovConfig {
    pub(crate) const VF_NAMING_PREFIX: &'static str = "sriov:";
    pub(crate) const VF_NAMING_SEPERATOR: char = ':';

    pub fn new() -> Self {
        Self::default()
    }

    // * Convert VF MAC address to upper case
    // * Sort by VF ID
    pub(crate) fn sanitize(&mut self) -> Result<(), NmstateError> {
        if let Some(vfs) = self.vfs.as_mut() {
            for vf in vfs.iter_mut() {
                if let Some(address) = vf.mac_address.as_mut() {
                    address.make_ascii_uppercase()
                }

                if let Some(VlanProtocol::Ieee8021Ad) = vf.vlan_proto {
                    if vf.vlan_id.unwrap_or_default() == 0
                        && vf.qos.unwrap_or_default() == 0
                    {
                        let e = NmstateError::new(
                                ErrorKind::InvalidArgument,
                                "VLAN protocol 802.1ad is not allowed when both VLAN ID and VLAN QoS are zero or unset"
                                    .to_string(),);
                        log::error!("VF ID {}: {}", vf.id, e);
                        return Err(e);
                    }
                }
            }
            vfs.sort_unstable_by(|a, b| a.id.cmp(&b.id));
        }

        Ok(())
    }

    // * Auto fill unmentioned VF ID
    pub(crate) fn auto_fill_unmentioned_vf_id(
        &mut self,
        current: Option<&Self>,
    ) {
        if let Some(vfs) = self.vfs.as_mut() {
            for vf in vfs.iter_mut() {
                if let Some(address) = vf.mac_address.as_mut() {
                    address.make_ascii_uppercase()
                }
            }
            vfs.sort_unstable_by(|a, b| a.id.cmp(&b.id));

            if !vfs.is_empty() {
                let total_vfs = self.total_vfs.unwrap_or_else(|| {
                    current.and_then(|c| c.total_vfs).unwrap_or(
                        vfs.iter().map(|v| v.id).max().unwrap_or_default() + 1,
                    )
                });
                self.total_vfs = Some(total_vfs);
                // Auto fill the missing
                if total_vfs as usize != vfs.len() {
                    let mut new_vf_confs: Vec<SrIovVfConfig> = (0..total_vfs)
                        .map(|i| {
                            let mut vf_conf = SrIovVfConfig::new();
                            vf_conf.id = i;
                            vf_conf
                        })
                        .collect();
                    for vf in vfs {
                        if new_vf_confs.len() > vf.id as usize {
                            new_vf_confs[vf.id as usize] = vf.clone();
                        }
                    }
                    self.vfs = Some(new_vf_confs);
                }
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct SrIovVfConfig {
    #[serde(deserialize_with = "crate::deserializer::u32_or_string")]
    pub id: u32,
    /// Interface name for this VF, only for querying, will be ignored
    /// when applying network state.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub iface_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Deserialize and serialize from/to `mac-address`.
    pub mac_address: Option<String>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    /// Deserialize and serialize from/to `spoof-check`.
    pub spoof_check: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub trust: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Deserialize and serialize from/to `min_tx_rate`.
    pub min_tx_rate: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Deserialize and serialize from/to `max-tx-rate`.
    pub max_tx_rate: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Deserialize and serialize from/to `vlan-id`.
    pub vlan_id: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub qos: Option<u32>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub vlan_proto: Option<VlanProtocol>,
}

impl SrIovVfConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

impl Interfaces {
    pub(crate) fn resolve_sriov_reference(
        &mut self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        self.resolve_sriov_reference_iface_name(current)?;
        self.resolve_sriov_reference_port_name(current)?;
        Ok(())
    }

    fn resolve_sriov_reference_iface_name(
        &mut self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        let mut changed_iface_names: Vec<String> = Vec::new();
        for iface in self.kernel_ifaces.values_mut() {
            if let Some((pf_name, vf_id)) = parse_sriov_vf_naming(iface.name())?
            {
                if let Some(vf_iface_name) =
                    get_sriov_vf_iface_name(current, pf_name, vf_id)
                {
                    changed_iface_names.push(iface.name().to_string());
                    log::info!(
                        "SR-IOV VF {} resolved to interface name {}",
                        iface.name(),
                        vf_iface_name
                    );
                    iface.base_iface_mut().name = vf_iface_name;
                } else {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Failed to find SR-IOV VF interface name for {}",
                            iface.name()
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
        }
        for changed_iface_name in changed_iface_names {
            if let Some(iface) = self.kernel_ifaces.remove(&changed_iface_name)
            {
                if self.kernel_ifaces.get(iface.name()).is_some() {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "SR-IOV VF name {} has been resolved as interface \
                            {}, but it is already defined in desire state",
                            changed_iface_name,
                            iface.name()
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
                self.kernel_ifaces.insert(iface.name().to_string(), iface);
            }
        }
        Ok(())
    }

    fn resolve_sriov_reference_port_name(
        &mut self,
        current: &Self,
    ) -> Result<(), NmstateError> {
        //  pending_changes:
        //      Vec<(ctrl_name, ctrl_iface_type, origin_name, new_name)>
        let mut pending_changes = Vec::new();
        for iface in self
            .kernel_ifaces
            .values()
            .chain(self.user_ifaces.values())
            .filter(|i| i.is_controller())
        {
            let ports = match iface.ports() {
                Some(p) => p,
                None => continue,
            };
            for port in ports {
                if let Some((pf_name, vf_id)) = parse_sriov_vf_naming(port)? {
                    if let Some(vf_iface_name) =
                        get_sriov_vf_iface_name(current, pf_name, vf_id)
                    {
                        log::info!(
                            "SR-IOV VF {} resolved to interface name {}",
                            port,
                            vf_iface_name
                        );
                        pending_changes.push((
                            iface.name().to_string(),
                            iface.iface_type(),
                            port.to_string(),
                            vf_iface_name.to_string(),
                        ));
                    } else {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Failed to find SR-IOV VF interface \
                                name for {}",
                                iface.name()
                            ),
                        ));
                    }
                }
            }
        }
        for (ctrl, ctrl_iface_type, origin_name, new_name) in pending_changes {
            if let Some(iface) = self.get_iface_mut(&ctrl, ctrl_iface_type) {
                iface.change_port_name(origin_name.as_str(), new_name);
            }
        }
        Ok(())
    }
}

fn parse_sriov_vf_naming(
    iface_name: &str,
) -> Result<Option<(&str, u32)>, NmstateError> {
    if iface_name.starts_with(SrIovConfig::VF_NAMING_PREFIX) {
        let names: Vec<&str> =
            iface_name.split(SrIovConfig::VF_NAMING_SEPERATOR).collect();
        if names.len() == 3 {
            match names[2].parse::<u32>() {
                Ok(vf_id) => Ok(Some((names[1], vf_id))),
                Err(e) => {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Invalid SR-IOV VF ID in {iface_name}, correct format \
                            is 'sriov:<pf_name>:<vf_id>', error: {e}"
                        ),
                    );
                    log::error!("{}", e);
                    Err(e)
                }
            }
        } else {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Invalid SR-IOV VF name {iface_name}, correct format is \
                    'sriov:<pf_name>:<vf_id>'",
                ),
            );
            log::error!("{}", e);
            Err(e)
        }
    } else {
        Ok(None)
    }
}

fn get_sriov_vf_iface_name(
    current: &Interfaces,
    pf_name: &str,
    vf_id: u32,
) -> Option<String> {
    if let Some(Interface::Ethernet(pf_iface)) =
        current.get_iface(pf_name, InterfaceType::Ethernet)
    {
        if let Some(vfs) = pf_iface
            .ethernet
            .as_ref()
            .and_then(|e| e.sr_iov.as_ref())
            .and_then(|s| s.vfs.as_ref())
        {
            for vf in vfs {
                if vf.id == vf_id {
                    if !vf.iface_name.is_empty() {
                        return Some(vf.iface_name.clone());
                    }
                    break;
                }
            }
        }
    }
    None
}

impl MergedInterface {
    pub(crate) fn post_inter_ifaces_process_sriov(
        &mut self,
    ) -> Result<(), NmstateError> {
        if let (
            Some(Interface::Ethernet(apply_iface)),
            Some(Interface::Ethernet(verify_iface)),
            Some(Interface::Ethernet(cur_iface)),
        ) = (
            self.for_apply.as_mut(),
            self.for_verify.as_mut(),
            self.current.as_ref(),
        ) {
            let cur_conf =
                cur_iface.ethernet.as_ref().and_then(|e| e.sr_iov.as_ref());
            if let (Some(apply_conf), Some(verify_conf)) = (
                apply_iface
                    .ethernet
                    .as_mut()
                    .and_then(|e| e.sr_iov.as_mut()),
                verify_iface
                    .ethernet
                    .as_mut()
                    .and_then(|e| e.sr_iov.as_mut()),
            ) {
                apply_conf.auto_fill_unmentioned_vf_id(cur_conf);
                verify_conf.auto_fill_unmentioned_vf_id(cur_conf);
            }
        }
        Ok(())
    }
}
