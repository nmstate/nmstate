// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize, Serializer};

use crate::{BaseInterface, InterfaceType};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
/// IP over InfiniBand interface. The example yaml output of a
/// [crate::NetworkState] with an infiniband interface would be:
/// ```yaml
/// ---
/// interfaces:
///   - name: ib2.8001
///     type: infiniband
///     state: up
///     mtu: 1280
///     infiniband:
///       pkey: "0x8001"
///       mode: "connected"
///       base-iface: "ib2"
/// ```
pub struct InfiniBandInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none", rename = "infiniband")]
    pub ib: Option<InfiniBandConfig>,
}

impl Default for InfiniBandInterface {
    fn default() -> Self {
        let mut base = BaseInterface::new();
        base.iface_type = InterfaceType::InfiniBand;
        Self { base, ib: None }
    }
}

impl InfiniBandInterface {
    pub(crate) fn parent(&self) -> Option<&str> {
        self.ib.as_ref().and_then(|cfg| cfg.base_iface.as_deref())
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum InfiniBandMode {
    /// Deserialize and serialize from/to `datagram`.
    Datagram,
    /// Deserialize and serialize from/to `connected`.
    Connected,
}

impl Default for InfiniBandMode {
    fn default() -> Self {
        Self::Datagram
    }
}

impl std::fmt::Display for InfiniBandMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                InfiniBandMode::Datagram => "datagram",
                InfiniBandMode::Connected => "connected",
            }
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct InfiniBandConfig {
    /// Mode of InfiniBand interface.
    pub mode: InfiniBandMode,
    #[serde(skip_serializing_if = "crate::serializer::is_option_string_empty")]
    /// For pkey sub-interface only. Empty for base interface.
    pub base_iface: Option<String>,
    #[serde(
        serialize_with = "show_as_hex",
        deserialize_with = "crate::deserializer::option_u16_or_string"
    )]
    /// P-key of sub-interface.
    /// Serialize in hex string format(lower case).
    /// For base interface, it is set to None.
    /// The `0xffff` value also indicate this is a InfiniBand base interface.
    pub pkey: Option<u16>,
}

impl InfiniBandConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

fn show_as_hex<S>(v: &Option<u16>, s: S) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    if let Some(v) = v {
        s.serialize_str(&format!("{v:#02x}"))
    } else {
        s.serialize_none()
    }
}
