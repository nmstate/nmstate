// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, ErrorKind, Interface, InterfaceMatchRule, InterfaceType,
    MergedInterface, NmstateError,
};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
/// Linux kernel Virtual Routing and Forwarding(VRF) interface. The example
/// yaml output of a [crate::NetworkState] with a VRF interface would be:
/// ```yml
/// interfaces:
/// - name: vrf0
///   type: vrf
///   state: up
///   mac-address: 42:6C:4A:0B:A3:C0
///   mtu: 65575
///   min-mtu: 1280
///   max-mtu: 65575
///   wait-ip: any
///   ipv4:
///     enabled: false
///   ipv6:
///     enabled: false
///   accept-all-mac-addresses: false
///   vrf:
///     port:
///     - eth1
///     - eth2
///     route-table-id: 100
/// ```
pub struct VrfInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vrf: Option<VrfConfig>,
}

impl Default for VrfInterface {
    fn default() -> Self {
        Self {
            base: BaseInterface {
                iface_type: InterfaceType::Vrf,
                ..Default::default()
            },
            vrf: None,
        }
    }
}

impl VrfInterface {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn ports(&self) -> Option<Vec<&str>> {
        if let Some(vrf_conf) = self.vrf.as_ref() {
            if vrf_conf.ports_config.is_some() {
                vrf_conf.ports_config.as_ref().map(|ports_config| {
                    ports_config
                        .as_slice()
                        .iter()
                        .filter_map(|p| {
                            if p.name.is_empty() {
                                None
                            } else {
                                Some(p.name.as_str())
                            }
                        })
                        .collect()
                })
            } else {
                vrf_conf.port.as_ref().map(|ports| {
                    ports
                        .as_slice()
                        .iter()
                        .filter_map(|p| {
                            if p.is_empty() {
                                None
                            } else {
                                Some(p.as_str())
                            }
                        })
                        .collect()
                })
            }
        } else {
            None
        }
    }

    pub(crate) fn sanitize(
        &mut self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        // Ignoring the changes of MAC address of VRF as it is a layer 3
        // interface.
        if is_desired {
            if let Some(mac) = self.base.mac_address.as_ref() {
                log::warn!(
                    "Ignoring MAC address {mac} of VRF interface {} \
                    as it is a layer 3(IP) interface",
                    self.base.name.as_str()
                );
            }
        }
        self.base.mac_address = None;
        if self.base.accept_all_mac_addresses == Some(false) {
            self.base.accept_all_mac_addresses = None;
        }

        let mut desired_ports: Option<Vec<String>> = None;
        let mut desired_ports_config_names: Option<Vec<String>> = None;

        // Sort ports
        if let Some(ports) = self.vrf.as_mut().and_then(|c| c.port.as_mut()) {
            ports.sort_unstable();
            if is_desired {
                desired_ports = Some(ports.clone());
            }
        }

        // Sort ports_config
        if let Some(ports_conf) =
            self.vrf.as_mut().and_then(|c| c.ports_config.as_mut())
        {
            ports_conf.sort_unstable_by_key(|p| p.name.to_string());
            if is_desired {
                desired_ports_config_names = Some(
                    ports_conf.iter().map(|p| p.name.to_string()).collect(),
                );
            }
        }

        // Validate consistence between `ports_config` and `ports`
        if is_desired
            && desired_ports.is_some()
            && desired_ports_config_names.is_some()
            && desired_ports != desired_ports_config_names
        {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "The VRF {} is holding inconsistent ports \
                            config in `port` and `ports-config` section: \
                            {} vs {}",
                    self.base.name,
                    desired_ports.unwrap_or_default().as_slice().join(","),
                    desired_ports_config_names
                        .unwrap_or_default()
                        .as_slice()
                        .join(",")
                ),
            ));
        }

        if let Some(vrf_conf) = self.vrf.as_mut() {
            // Unify the `ports_config` and `ports`
            if vrf_conf.port.is_some() || vrf_conf.ports_config.is_some() {
                if vrf_conf.port.is_none() {
                    vrf_conf.port = desired_ports_config_names;
                }
                if vrf_conf.ports_config.is_none() {
                    vrf_conf.ports_config = desired_ports.map(|ports| {
                        ports
                            .into_iter()
                            .map(|p| VrfPortConfig {
                                name: p,
                                ..Default::default()
                            })
                            .collect()
                    });
                }
            }
            if let Some(ports_config) = vrf_conf.ports_config.as_mut() {
                for port_config in ports_config {
                    port_config.sanitize();
                }
            }
        }

        Ok(())
    }

    pub(crate) fn merge_table_id(
        &mut self,
        current: Option<&Interface>,
    ) -> Result<(), NmstateError> {
        if self
            .vrf
            .as_ref()
            .and_then(|v| v.table_id)
            .unwrap_or_default()
            == 0
        {
            if let Some(cur_table_id) =
                if let Some(Interface::Vrf(vrf_iface)) = current {
                    vrf_iface.vrf.as_ref().and_then(|v| v.table_id)
                } else {
                    None
                }
            {
                if let Some(vrf_conf) = self.vrf.as_mut() {
                    vrf_conf.table_id = Some(cur_table_id);
                }
            } else {
                let e = NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Route table ID undefined or 0 is not allowed for \
                        new VRF interface {}",
                        self.base.name
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
        Ok(())
    }

    pub(crate) fn resolve_iface_match(
        &mut self,
        cache: &crate::ifaces::IfaceMatchCache,
    ) -> Result<(), NmstateError> {
        if let Some(ports_config) = self
            .vrf
            .as_mut()
            .and_then(|b| b.ports_config.as_deref_mut())
        {
            for port_conf in
                ports_config.iter_mut().filter(|p| p.iface_match.is_some())
            {
                if let Some(iface_match) = port_conf.iface_match.as_ref() {
                    log::info!("Searching VRF port by rule {iface_match}",);
                    let new_name = iface_match.resolve(cache)?;
                    if port_conf.name.is_empty() {
                        log::info!(
                            "VRF port for rule {iface_match} is {new_name}",
                        );
                        port_conf.name = new_name;
                    } else if port_conf.name != new_name {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "VRF interface {} has port holding \
                                both name {} and match {}, but the \
                                matched interface is {}",
                                self.base.name.as_str(),
                                port_conf.name,
                                iface_match,
                                new_name
                            ),
                        ));
                    }
                }
            }
        }

        Ok(())
    }

    pub(crate) fn port_iface_matches(
        &self,
    ) -> HashMap<String, InterfaceMatchRule> {
        let mut ret: HashMap<String, InterfaceMatchRule> = HashMap::new();
        if let Some(ports_config) =
            self.vrf.as_ref().and_then(|v| v.ports_config.as_ref())
        {
            for port_config in ports_config.as_slice() {
                if let Some(iface_match) = port_config.iface_match.as_ref() {
                    ret.insert(port_config.name.clone(), iface_match.clone());
                }
            }
        }
        ret
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
pub struct VrfConfig {
    #[serde(alias = "ports", skip_serializing_if = "Option::is_none")]
    /// Port list.
    /// Deserialize and serialize from/to `port`.
    /// Also deserialize from `ports`.
    pub port: Option<Vec<String>>,
    #[serde(
        rename = "route-table-id",
        default,
        skip_serializing_if = "Option::is_none",
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    /// Route table ID of this VRF interface.
    /// Deserialize and serialize from/to `route-table-id`.
    pub table_id: Option<u32>,
    #[serde(rename = "ports-config", skip_serializing_if = "Option::is_none")]
    pub ports_config: Option<Vec<VrfPortConfig>>,
}

impl MergedInterface {
    // Merge table ID from current if desired table ID is 0
    pub(crate) fn post_inter_ifaces_process_vrf(
        &mut self,
    ) -> Result<(), NmstateError> {
        if !self.merged.is_absent() {
            if let Some(Interface::Vrf(apply_iface)) = self.for_apply.as_mut() {
                apply_iface.merge_table_id(self.current.as_ref())?;
            }
            if let Some(Interface::Vrf(verify_iface)) = self.for_verify.as_mut()
            {
                verify_iface.merge_table_id(self.current.as_ref())?;
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct VrfPortConfig {
    /// The kernel interface name of VRF port.
    /// When applying with both `name` and `match` section defined,
    /// pre-apply validation will raise if they are not pointing to the same
    /// interface, and the `name` will not stored into persistent configuration
    /// storage.
    #[serde(skip_serializing_if = "String::is_empty", default)]
    pub name: String,
    /// Rule to matching interface as VRF port.
    #[serde(skip_serializing_if = "Option::is_none", rename = "match")]
    pub iface_match: Option<InterfaceMatchRule>,
}

impl VrfPortConfig {
    pub(crate) fn sanitize(&mut self) {
        if let Some(iface_match) = self.iface_match.as_mut() {
            iface_match.sanitize();
        }
    }
}
