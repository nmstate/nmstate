// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, ErrorKind, InterfaceType, NmstateError};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// Linux kernel IPVLAN interface. The example YAML output of
/// [crate::NetworkState] with an IPVLAN interface would be:
/// ```yaml
/// ---
/// interfaces:
///   - name: ipvlan0
///     type: ipvlan
///     state: up
///     ipvlan:
///       base-iface: eth1
///       mode: l3
///       private: true
/// ```
pub struct IpVlanInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ipvlan: Option<IpVlanConfig>,
}

impl Default for IpVlanInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::IpVlan,
                ..Default::default()
            },
            ipvlan: None,
        }
    }
}

impl IpVlanInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn sanitize(
        &self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if is_desired {
            if let Some(conf) = &self.ipvlan {
                if conf.private == Some(true) && conf.vepa == Some(true) {
                    let e = NmstateError::new(
                        ErrorKind::InvalidArgument,
                        "Both private and VEPA flags cannot \
                    be enabled at the same time"
                            .to_string(),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct IpVlanConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub base_iface: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub mode: Option<IpVlanMode>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub private: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub vepa: Option<bool>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum IpVlanMode {
    /// Deserialize and serialize from/to `l2`.
    L2,
    /// Deserialize and serialize from/to `l3`.
    L3,
    #[serde(rename = "l3s")]
    /// Deserialize and serialize from/to `l3s`.
    L3S,
}

impl From<IpVlanMode> for u32 {
    fn from(v: IpVlanMode) -> u32 {
        match v {
            IpVlanMode::L2 => 1,
            IpVlanMode::L3 => 2,
            IpVlanMode::L3S => 3,
        }
    }
}

impl Default for IpVlanMode {
    fn default() -> Self {
        Self::L3
    }
}
