// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, InterfaceType};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct VxlanInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vxlan: Option<VxlanConfig>,
}

impl Default for VxlanInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::Vxlan,
                ..Default::default()
            },
            vxlan: None,
        }
    }
}

impl VxlanInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn parent(&self) -> Option<&str> {
        self.vxlan.as_ref().map(|cfg| cfg.base_iface.as_str())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct VxlanConfig {
    pub base_iface: String,
    #[serde(deserialize_with = "crate::deserializer::u32_or_string")]
    pub id: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub remote: Option<std::net::IpAddr>,
    #[serde(
        rename = "destination-port",
        default,
        deserialize_with = "crate::deserializer::option_u16_or_string"
    )]
    pub dst_port: Option<u16>,
}
