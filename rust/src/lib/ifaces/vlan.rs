// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, ErrorKind, Interface, InterfaceType, MergedInterface,
    NmstateError,
};

/// The maximum of VLAN priority is 7 according to
/// 802.1Q-2018 PCP field definition.
const MAX_VLAN_PRIORITY: u32 = 7;

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
        if let Some(vlan_conf) = self.vlan.as_mut() {
            if let Some(maps) = vlan_conf.ingress_qos_map.as_mut() {
                maps.sort_unstable()
            }
            if let Some(maps) = vlan_conf.egress_qos_map.as_mut() {
                maps.sort_unstable()
            }
            if is_desired {
                if vlan_conf.base_iface.is_none() {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Missing 'vlan.base-iface' for interface '{}'",
                            &self.base.name
                        ),
                    ));
                }
                if let Some(maps) = vlan_conf.ingress_qos_map.as_ref() {
                    for in_map in maps.as_slice() {
                        if in_map.from > MAX_VLAN_PRIORITY {
                            return Err(NmstateError::new(
                                ErrorKind::InvalidArgument,
                                format!(
                                    "The maximum VLAN priority is 7, but got \
                                     VLAN {} ingress qos map from value set \
                                     as {}",
                                    self.base.name.as_str(),
                                    in_map.from
                                ),
                            ));
                        }
                    }
                }
                if let Some(maps) = vlan_conf.egress_qos_map.as_ref() {
                    for eg_map in maps.as_slice() {
                        if eg_map.to > MAX_VLAN_PRIORITY {
                            return Err(NmstateError::new(
                                ErrorKind::InvalidArgument,
                                format!(
                                    "The maximum VLAN priority is 7, but got \
                                     VLAN {} egress qos map to value set as {}",
                                    self.base.name.as_str(),
                                    eg_map.to
                                ),
                            ));
                        }
                    }
                }
            }
        }
        Ok(())
    }

    pub(crate) fn change_parent_name(&mut self, name: &str) {
        if let Some(vlan_conf) = self.vlan.as_mut() {
            vlan_conf.base_iface = Some(name.to_string());
        }
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
    /// Mapping VLAN header priority to linux internal packet priority for
    /// incoming packet.
    /// The maximum of VLAN priority is 7 according to
    /// 802.1Q-2018 PCP field definition.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ingress_qos_map: Option<Vec<VlanQosMapping>>,
    /// Mapping linux internal packet priority to VLAN header priority for
    /// outgoing packet.
    /// The maximum of VLAN priority is 7 according to
    /// 802.1Q-2018 PCP field definition.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub egress_qos_map: Option<Vec<VlanQosMapping>>,
}

#[derive(
    Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default,
)]
pub enum VlanProtocol {
    #[serde(rename = "802.1q")]
    /// Deserialize and serialize from/to `802.1q`.
    #[default]
    Ieee8021Q,
    #[serde(rename = "802.1ad")]
    /// Deserialize and serialize from/to `802.1ad`.
    Ieee8021Ad,
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
                    && let Some(vlan_conf) = apply_iface.vlan.as_mut()
                    && vlan_conf.reorder_headers.is_none()
                {
                    vlan_conf.reorder_headers = Some(true);
                }
            } else if let Some(vlan_conf) = apply_iface.vlan.as_mut()
                && vlan_conf.reorder_headers.is_none()
            {
                vlan_conf.reorder_headers = Some(true);
            }
        }

        if let (
            Some(Interface::Vlan(apply_iface)),
            Some(Interface::Vlan(verify_iface)),
            Some(Interface::Vlan(cur_iface)),
        ) = (&mut self.for_apply, &mut self.for_verify, &self.current)
        {
            if let Some(apply_vlan) = &mut apply_iface.vlan
                && apply_vlan.base_iface.is_none()
            {
                apply_vlan.base_iface = cur_iface
                    .vlan
                    .as_ref()
                    .and_then(|vlan| vlan.base_iface.clone());
            }
            if let Some(verify_vlan) = &mut verify_iface.vlan
                && verify_vlan.base_iface.is_none()
            {
                verify_vlan.base_iface = cur_iface
                    .vlan
                    .as_ref()
                    .and_then(|vlan| vlan.base_iface.clone());
            }
        }
    }
}

/// VLAN QoS Mapping
/// Mapping between linux internal packet priority and VLAN header priority for
/// incoming or outgoing packet.
#[derive(
    Serialize, Deserialize, Debug, PartialEq, Eq, Clone, Copy, Default,
)]
pub struct VlanQosMapping {
    #[serde(deserialize_with = "crate::deserializer::u32_or_string")]
    pub from: u32,
    #[serde(deserialize_with = "crate::deserializer::u32_or_string")]
    pub to: u32,
}

impl std::fmt::Display for VlanQosMapping {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}:{}", self.from, self.to)
    }
}

// For Ord
impl PartialOrd for VlanQosMapping {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

// For Vec::sort_unstable()
impl Ord for VlanQosMapping {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        (self.from, self.to).cmp(&(other.from, other.to))
    }
}
