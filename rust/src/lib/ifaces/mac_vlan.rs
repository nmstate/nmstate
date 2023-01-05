// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, ErrorKind, InterfaceType, NmstateError};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// Linux kernel MAC VLAN interface. The example yaml output of
/// [crate::NetworkState] with a mac vlan interface would be:
/// ```yaml
/// ---
/// interfaces:
///   - name: mac0
///     type: mac-vlan
///     state: up
///     mac-vlan:
///       base-iface: eth1
///       mode: vepa
///       promiscuous: true
/// ```
pub struct MacVlanInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none", rename = "mac-vlan")]
    /// Deserialize and serialize from/to `mac-vlan`.
    pub mac_vlan: Option<MacVlanConfig>,
}

impl Default for MacVlanInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::MacVlan,
                ..Default::default()
            },
            mac_vlan: None,
        }
    }
}

impl MacVlanInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn sanitize(&self) -> Result<(), NmstateError> {
        if let Some(conf) = &self.mac_vlan {
            if conf.accept_all_mac == Some(false)
                && conf.mode != MacVlanMode::Passthru
            {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    "Disable accept-all-mac-addresses(promiscuous) \
                    is only allowed on passthru mode"
                        .to_string(),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
        Ok(())
    }

    pub(crate) fn parent(&self) -> Option<&str> {
        self.mac_vlan.as_ref().map(|cfg| cfg.base_iface.as_str())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct MacVlanConfig {
    pub base_iface: String,
    pub mode: MacVlanMode,
    #[serde(
        skip_serializing_if = "Option::is_none",
        rename = "promiscuous",
        alias = "accept-all-mac",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    /// Serialize to `promiscuous`.
    /// Deserialize from `promiscuous` or `accept-all-mac`.
    pub accept_all_mac: Option<bool>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum MacVlanMode {
    /// Deserialize and serialize from/to `vepa`.
    Vepa,
    /// Deserialize and serialize from/to `bridge`.
    Bridge,
    /// Deserialize and serialize from/to `private`.
    Private,
    /// Deserialize and serialize from/to `passthru`.
    Passthru,
    /// Deserialize and serialize from/to `source`.
    Source,
    Unknown,
}

impl From<MacVlanMode> for u32 {
    fn from(v: MacVlanMode) -> u32 {
        match v {
            MacVlanMode::Unknown => 0,
            MacVlanMode::Vepa => 1,
            MacVlanMode::Bridge => 2,
            MacVlanMode::Private => 3,
            MacVlanMode::Passthru => 4,
            MacVlanMode::Source => 5,
        }
    }
}

impl Default for MacVlanMode {
    fn default() -> Self {
        Self::Unknown
    }
}
