// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{ErrorKind, Interface, Interfaces, NmstateError};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct SrIovConfig {
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub total_vfs: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vfs: Option<Vec<SrIovVfConfig>>,
}

impl SrIovConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn sriov_is_enabled(&self) -> bool {
        matches!(self.total_vfs, Some(i) if i > 0)
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
    pub mac_address: Option<String>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
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
    pub min_tx_rate: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub max_tx_rate: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
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
    let path = format!("/sys/class/net/{}/device/sriov_numvfs", iface_name);
    std::path::Path::new(&path).exists()
}
