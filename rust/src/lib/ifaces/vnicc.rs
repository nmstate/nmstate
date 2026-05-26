// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
/// Virtual NIC Characteristics (VNICC) configuration for s390x qeth devices.
/// The VNICC settings are exposed via sysfs at
/// `/sys/class/net/<iface>/vnicc/`.
///
/// The example yaml output of [crate::NetworkState] with VNICC enabled
/// ethernet interface would be:
/// ```yml
/// interfaces:
/// - name: enc600
///   type: ethernet
///   state: up
///   ethernet:
///     vnicc:
///       bridge-invisible: true
///       learning: false
/// ```
pub struct VniccConfig {
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    /// Whether the adapter is invisible to software bridges.
    /// When enabled, the device does not participate in bridge MAC learning
    /// or forwarding decisions.
    /// Deserialize and serialize from/to `bridge-invisible`.
    pub bridge_invisible: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    /// Whether the device performs MAC address learning.
    pub learning: Option<bool>,
}

impl VniccConfig {
    pub fn new() -> Self {
        Self::default()
    }
}
