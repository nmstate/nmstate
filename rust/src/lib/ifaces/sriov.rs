// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{ErrorKind, Interface, Interfaces, NmstateError};

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
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn sriov_is_enabled(&self) -> bool {
        matches!(self.total_vfs, Some(i) if i > 0)
    }

    // * Convert VF MAC address to upper case
    // * Sort by VF ID
    // * Ignore 'vfs: []' which is just reverting all VF config to default.
    // * Auto fill unmentioned VF ID
    pub(crate) fn pre_edit_cleanup(&mut self, current: Option<&Self>) {
        if let Some(vfs) = self.vfs.as_mut() {
            for vf in vfs.iter_mut() {
                if let Some(address) = vf.mac_address.as_mut() {
                    address.make_ascii_uppercase()
                }
            }
            vfs.sort_unstable_by(|a, b| a.id.cmp(&b.id));

            if !vfs.is_empty() {
                let total_vfs = self.total_vfs.unwrap_or(
                    current.and_then(|c| c.total_vfs).unwrap_or(
                        vfs.iter().map(|v| v.id).max().unwrap_or_default() + 1,
                    ),
                );
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
    #[serde(skip)]
    pub(crate) iface_name: String,
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
}

impl SrIovVfConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

pub(crate) fn check_sriov_capability(
    ifaces: &Interfaces,
) -> Result<(), NmstateError> {
    for iface in ifaces.kernel_ifaces.values() {
        if let Interface::Ethernet(eth_iface) = iface {
            if eth_iface.sriov_is_enabled() && !is_sriov_supported(iface.name())
            {
                let e = NmstateError::new(
                    ErrorKind::NotSupportedError,
                    format!(
                        "SR-IOV is not supported by interface {}",
                        iface.name()
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
    }
    Ok(())
}

// Checking existence of file:
//      /sys/class/net/<iface_name>/device/sriov_numvfs
fn is_sriov_supported(iface_name: &str) -> bool {
    let path = format!("/sys/class/net/{iface_name}/device/sriov_numvfs");
    std::path::Path::new(&path).exists()
}
