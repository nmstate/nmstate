// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, ErrorKind, Interface, InterfaceType, MergedInterface,
    NmstateError,
};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// Linux kernel VLAN interface. The example yaml output of
/// [crate::NetworkState] with a VLAN interface would be:
/// ```yaml
/// interfaces:
/// - name: eth1.101
///   type: vlan
///   state: up
///   mac-address: BE:E8:17:8F:D2:70
///   mtu: 1500
///   max-mtu: 65535
///   wait-ip: any
///   ipv4:
///     enabled: false
///   ipv6:
///     enabled: false
///   accept-all-mac-addresses: false
///   vlan:
///     base-iface: eth1
///     id: 101
/// ```
pub struct VlanInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vlan: Option<VlanConfig>,
}

impl Default for VlanInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::Vlan,
                ..Default::default()
            },
            vlan: None,
        }
    }
}

impl VlanInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub(crate) fn parent(&self) -> Option<&str> {
        self.vlan
            .as_ref()
            .and_then(|cfg| cfg.base_iface.as_ref())
            .map(|base_iface| base_iface.as_str())
    }

    pub(crate) fn sanitize(
        &mut self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if let Some(vlan_conf) = &self.vlan {
            if is_desired && vlan_conf.base_iface.is_none() {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Missing 'vlan.base-iface' for interface '{}'",
                        &self.base.name
                    ),
                ));
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct VlanConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub base_iface: Option<String>,
    #[serde(deserialize_with = "crate::deserializer::u16_or_string")]
    pub id: u16,
    /// Could be `802.1q` or `802.1ad`. Default to `802.1q` if not defined.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub protocol: Option<VlanProtocol>,
    /// Could be `gvrp`, `mvrp` or `none`. Default to none if not defined.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub registration_protocol: Option<VlanRegistrationProtocol>,
    /// reordering of output packet headers. Default to True if not defined.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reorder_headers: Option<bool>,
    /// loose binding of the interface to its master device's operating state
    #[serde(skip_serializing_if = "Option::is_none")]
    pub loose_binding: Option<bool>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum VlanProtocol {
    #[serde(rename = "802.1q")]
    /// Deserialize and serialize from/to `802.1q`.
    Ieee8021Q,
    #[serde(rename = "802.1ad")]
    /// Deserialize and serialize from/to `802.1ad`.
    Ieee8021Ad,
}

impl Default for VlanProtocol {
    fn default() -> Self {
        Self::Ieee8021Q
    }
}

impl std::fmt::Display for VlanProtocol {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Ieee8021Q => "802.1q",
                Self::Ieee8021Ad => "802.1ad",
            }
        )
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum VlanRegistrationProtocol {
    /// GARP VLAN Registration Protocol
    Gvrp,
    /// Multiple VLAN Registration Protocol
    Mvrp,
    /// No Registration Protocol
    None,
}

impl MergedInterface {
    // Default reorder_headers to Some(true) unless current interface
    // has `reorder_headers` set to `false`.
    // If base-iface is not defined in the desired state, take it from the
    // current state.
    pub(crate) fn post_inter_ifaces_process_vlan(&mut self) {
        if let Some(Interface::Vlan(apply_iface)) = self.for_apply.as_mut() {
            if let Some(Interface::Vlan(cur_iface)) = self.current.as_ref() {
                if cur_iface
                    .vlan
                    .as_ref()
                    .and_then(|v| v.reorder_headers.as_ref())
                    != Some(&false)
                {
                    if let Some(vlan_conf) = apply_iface.vlan.as_mut() {
                        if vlan_conf.reorder_headers.is_none() {
                            vlan_conf.reorder_headers = Some(true);
                        }
                    }
                }
            } else if let Some(vlan_conf) = apply_iface.vlan.as_mut() {
                if vlan_conf.reorder_headers.is_none() {
                    vlan_conf.reorder_headers = Some(true);
                }
            }
        }

        if let (
            Some(Interface::Vlan(apply_iface)),
            Some(Interface::Vlan(verify_iface)),
            Some(Interface::Vlan(cur_iface)),
        ) = (&mut self.for_apply, &mut self.for_verify, &self.current)
        {
            if let Some(apply_vlan) = &mut apply_iface.vlan {
                if apply_vlan.base_iface.is_none() {
                    apply_vlan.base_iface = cur_iface
                        .vlan
                        .as_ref()
                        .and_then(|vlan| vlan.base_iface.clone());
                }
            }
            if let Some(verify_vlan) = &mut verify_iface.vlan {
                if verify_vlan.base_iface.is_none() {
                    verify_vlan.base_iface = cur_iface
                        .vlan
                        .as_ref()
                        .and_then(|vlan| vlan.base_iface.clone());
                }
            }
        }
    }
}
