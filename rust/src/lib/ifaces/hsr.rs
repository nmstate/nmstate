// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{
    BaseInterface, ErrorKind, Interface, InterfaceIpv4, InterfaceIpv6,
    InterfaceState, InterfaceType, MergedInterface, MergedInterfaces,
    NmstateError,
};

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
///
/// nmstate will configure the MAC addresses of HSR ports
/// to be matching, to retain failover ability. It will
/// use the MAC address of port1 by default, and apply it
/// to port2 and the HSR interface. The MAC address can
/// be overridden by setting the `mac-address` property
/// on the HSR interface itself.
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

    pub(crate) fn ports(&self) -> Option<Vec<&str>> {
        self.hsr.as_ref().map(|hsr_conf| {
            vec![hsr_conf.port1.as_str(), hsr_conf.port2.as_str()]
        })
    }

    pub(crate) fn sanitize(
        &mut self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if is_desired
            && let Some(conf) = &mut self.hsr
            && let Some(address) = &mut conf.supervision_address
        {
            address.as_mut().make_ascii_uppercase();
            log::warn!(
                "The supervision-address is read-only, ignoring it on desired \
                 state."
            );
        }

        if is_desired
            && let Some(conf) = &mut self.hsr
            && conf.interlink.is_some()
            && conf.protocol == HsrProtocol::Prp
        {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "The interlink property is not supported on PRP interface \
                     {}",
                    self.base.name
                ),
            ));
        }

        Ok(())
    }
}

impl MergedInterfaces {
    pub(crate) fn get_hsr_mac(&self, iface: &HsrInterface) -> Option<String> {
        if iface.base.mac_address.is_some() {
            return iface.base.mac_address.clone();
        }

        let hsr_conf = iface.hsr.as_ref()?;

        for use_permanent in [false, true] {
            for port in [&hsr_conf.port1, &hsr_conf.port2] {
                let mac = self
                    .get_iface(port, InterfaceType::Unknown)
                    .and_then(|iface| {
                        let base = iface.merged.base_iface();
                        if use_permanent {
                            base.permanent_mac_address.clone()
                        } else {
                            base.mac_address.clone()
                        }
                    });
                if mac.is_some() {
                    return mac;
                }
            }
        }

        None
    }

    pub(crate) fn validate_hsr_mac(&self) -> Result<(), NmstateError> {
        for hsr_iface in self.kernel_ifaces.values().filter_map(|iface| {
            if let Interface::Hsr(hsr_iface) = iface.desired.as_ref()? {
                let hsr_conf = hsr_iface.hsr.as_ref()?;

                if hsr_conf.protocol == HsrProtocol::Prp {
                    return Some(hsr_iface);
                }
            }

            None
        }) {
            let macs = [
                hsr_iface.base.mac_address.as_deref(),
                hsr_iface
                    .hsr
                    .as_ref()
                    .and_then(|hsr_conf| {
                        self.get_iface(&hsr_conf.port1, InterfaceType::Unknown)
                    })
                    .and_then(|iface| iface.desired.as_ref())
                    .and_then(|iface| {
                        iface.base_iface().mac_address.as_deref()
                    }),
                hsr_iface
                    .hsr
                    .as_ref()
                    .and_then(|hsr_conf| {
                        self.get_iface(&hsr_conf.port2, InterfaceType::Unknown)
                    })
                    .and_then(|iface| iface.desired.as_ref())
                    .and_then(|iface| {
                        iface.base_iface().mac_address.as_deref()
                    }),
            ];

            let mut acc = None;

            for &mac in macs.iter().flatten() {
                if acc.is_some() && Some(mac) != acc {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "HSR ports on interface {} cannot have different \
                             MAC addresses",
                            hsr_iface.base.name
                        ),
                    ));
                }

                acc = Some(mac);
            }
        }

        Ok(())
    }

    pub(crate) fn copy_hsr_mac(&mut self) -> Result<(), NmstateError> {
        let mut pending_changes = Vec::new();

        for (hsr_iface, hsr_conf, mac) in
            self.kernel_ifaces.values().filter_map(|iface| {
                if !iface.is_desired() || !iface.merged.is_up() {
                    return None;
                }

                if let Interface::Hsr(hsr_iface) = &iface.merged {
                    let mac = self.get_hsr_mac(hsr_iface)?;
                    let hsr_conf = hsr_iface.hsr.as_ref()?;

                    if hsr_conf.protocol != HsrProtocol::Prp {
                        return None;
                    }

                    if iface.current.is_some() {
                        if Some(mac.as_str())
                            != self.kernel_ifaces.get(&hsr_conf.port2).and_then(
                                |iface| {
                                    iface
                                        .merged
                                        .base_iface()
                                        .mac_address
                                        .as_deref()
                                },
                            )
                        {
                            log::warn!(
                                "Existing HSR PRP interface {} has \
                                 mismatching MAC addresses on port1 and \
                                 port2, which may break functionality",
                                iface.merged.name()
                            );
                        }

                        return None;
                    }

                    return Some((hsr_iface, hsr_conf, mac));
                }

                None
            })
        {
            for ifname in
                [&hsr_iface.base.name, &hsr_conf.port1, &hsr_conf.port2]
            {
                pending_changes.push((ifname.clone(), mac.clone()));
            }
        }

        for (ifname, mac) in pending_changes {
            if let Some(iface) = self.kernel_ifaces.get_mut(&ifname) {
                iface.mark_as_changed();
                if let Some(for_apply) = iface.for_apply.as_mut() {
                    for_apply.base_iface_mut().state = InterfaceState::Up;
                }
                iface.merged.base_iface_mut().state = InterfaceState::Up;
                iface.set_copy_from_mac(mac.clone());
            }
        }

        Ok(())
    }
}

impl MergedInterface {
    /// Explicitly disable IP on HSR ports
    pub(crate) fn post_inter_ifaces_process_hsr(&mut self) {
        if let Some(apply_iface) = self.for_apply.as_mut()
            && apply_iface.is_up()
            && apply_iface.base_iface().controller_type.as_ref()
                == Some(&InterfaceType::Hsr)
        {
            apply_iface.base_iface_mut().ipv4 = Some(InterfaceIpv4 {
                enabled: false,
                ..Default::default()
            });
            apply_iface.base_iface_mut().ipv6 = Some(InterfaceIpv6 {
                enabled: false,
                ..Default::default()
            });
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
#[derive(Default)]
pub struct HsrConfig {
    /// The port1 interface name.
    pub port1: String,
    /// The port2 interface name.
    pub port2: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// The interlink interface name.
    pub interlink: Option<String>,
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
#[derive(Default)]
pub enum HsrProtocol {
    #[default]
    #[serde(alias = "hsr-2010")]
    Hsr,
    #[serde(rename = "hsr-2012")]
    Hsr2012,
    Prp,
}
