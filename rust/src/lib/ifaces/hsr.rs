// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType, NmstateError};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
/// HSR interface. The example YAML output of a
/// [crate::NetworkState] with an HSR interface would be:
/// ```yaml
/// ---
/// interfaces:
///   - name: hsr0
///     type: hsr
///     state: up
///     hsr:
///       port1: eth1
///       port2: eth2
///       multicast-spec: 40
///       protocol: prp
/// ```
pub struct HsrInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Deserialize and serialize to `hsr`.
    pub hsr: Option<HsrConfig>,
}

impl Default for HsrInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::Hsr,
                ..Default::default()
            },
            hsr: None,
        }
    }
}

impl HsrInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn sanitize(
        &mut self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if is_desired {
            if let Some(conf) = &mut self.hsr {
                if let Some(address) = &mut conf.supervision_address {
                    address.as_mut().make_ascii_uppercase();
                    log::warn!("The supervision-address is read-only, ignoring it on desired state.");
                }
            }
        }
        Ok(())
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
#[derive(Default)]
pub struct HsrConfig {
    /// The port1 interface name.
    pub port1: String,
    /// The port2 interface name.
    pub port2: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// The MAC address used for the supervision frames. This property is
    /// read-only.
    pub supervision_address: Option<String>,
    /// The last byte of the supervision address.
    pub multicast_spec: u8,
    /// Protocol to be used.
    pub protocol: HsrProtocol,
}

impl HsrConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum HsrProtocol {
    Hsr,
    Prp,
}

impl Default for HsrProtocol {
    fn default() -> Self {
        Self::Hsr
    }
}
