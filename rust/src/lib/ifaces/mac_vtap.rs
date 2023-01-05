// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, ErrorKind, InterfaceType, NmstateError};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// Linux kernel MAC VTAP interface. The example output of [crate::NetworkState]
/// with a mac vtap interface would be:
/// ```yml
/// ---
/// interfaces:
///   - name: mac0
///     type: mac-vtap
///     state: up
///     mac-vtap:
///       base-iface: eth1
///       mode: passthru
///       promiscuous: true
/// ```
pub struct MacVtapInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none", rename = "mac-vtap")]
    /// Deserialize and serialize from/to `mac-vtap`.
    pub mac_vtap: Option<MacVtapConfig>,
}

impl Default for MacVtapInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::MacVtap,
                ..Default::default()
            },
            mac_vtap: None,
        }
    }
}

impl MacVtapInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn sanitize(&self) -> Result<(), NmstateError> {
        if let Some(conf) = &self.mac_vtap {
            if conf.accept_all_mac == Some(false)
                && conf.mode != MacVtapMode::Passthru
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
        self.mac_vtap.as_ref().map(|cfg| cfg.base_iface.as_str())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct MacVtapConfig {
    pub base_iface: String,
    pub mode: MacVtapMode,
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
pub enum MacVtapMode {
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

impl From<MacVtapMode> for u32 {
    fn from(v: MacVtapMode) -> u32 {
        match v {
            MacVtapMode::Unknown => 0,
            MacVtapMode::Vepa => 1,
            MacVtapMode::Bridge => 2,
            MacVtapMode::Private => 3,
            MacVtapMode::Passthru => 4,
            MacVtapMode::Source => 5,
        }
    }
}

impl Default for MacVtapMode {
    fn default() -> Self {
        Self::Unknown
    }
}
