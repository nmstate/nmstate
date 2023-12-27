// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

use crate::{
    DispatchConfig, ErrorKind, EthtoolConfig, Ieee8021XConfig,
    InterfaceIdentifier, InterfaceIpv4, InterfaceIpv6, InterfaceState,
    InterfaceType, LldpConfig, MergedInterface, MptcpConfig, NmstateError,
    OvsDbIfaceConfig, RouteEntry, WaitIp,
};

const MINIMUM_IPV6_MTU: u64 = 1280;

// TODO: Use prop_list to Serialize like InterfaceIpv4 did
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
/// Information shared among all interface types
pub struct BaseInterface {
    /// Interface name, when applying with `InterfaceIdentifier::MacAddress`,
    /// if `profile_name` not defined, this will be used as profile name.
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile_name: Option<String>,
    #[serde(skip_serializing_if = "crate::serializer::is_option_string_empty")]
    /// Interface description stored in network backend. Not available for
    /// kernel only mode.
    pub description: Option<String>,
    #[serde(skip)]
    /// TODO: internal use only. Hide this.
    pub prop_list: Vec<&'static str>,
    #[serde(rename = "type", default = "default_iface_type")]
    /// Interface type. Serialize and deserialize to/from `type`
    pub iface_type: InterfaceType,
    #[serde(default = "default_state")]
    /// Interface state. Default to [InterfaceState::Up] when applying.
    pub state: InterfaceState,
    #[serde(default, skip_serializing_if = "InterfaceIdentifier::is_default")]
    /// Define network backend matching method on choosing network interface.
    /// Default to [InterfaceIdentifier::Name].
    pub identifier: InterfaceIdentifier,
    /// When applying with `[InterfaceIdentifier::MacAddress]`,
    /// nmstate will store original desired interface name as `profile_name`
    /// here and store the real interface name as `name` property.
    #[serde(skip_serializing_if = "Option::is_none")]
    /// For [InterfaceIdentifier::Name] (default), this property will change
    /// the interface MAC address to desired one when applying.
    /// For [InterfaceIdentifier::MacAddress], this property will be used
    /// for searching interface on desired MAC address when applying.
    /// MAC address in the format: upper case hex string separated by `:` on
    /// every two characters. Case insensitive when applying.
    /// Serialize and deserialize to/from `mac-address`.
    pub mac_address: Option<String>,
    #[serde(skip)]
    /// MAC address never change after reboots(normally stored in firmware of
    /// network interface). Using the same format as `mac_address` property.
    /// Ignored during apply.
    /// TODO: expose it and we do not special merge for this.
    pub permanent_mac_address: Option<String>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u64_or_string"
    )]
    /// Maximum transmission unit.
    pub mtu: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Minimum MTU allowed. Ignored during apply.
    /// Serialize and deserialize to/from `min-mtu`.
    pub min_mtu: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Maximum MTU allowed. Ignored during apply.
    /// Serialize and deserialize to/from `max-mtu`.
    pub max_mtu: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Whether system should wait certain IP stack before considering
    /// network interface activated.
    /// Serialize and deserialize to/from `wait-ip`.
    pub wait_ip: Option<WaitIp>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// IPv4 information.
    /// Hided if interface is not allowed to hold IP information(e.g. port of
    /// bond is not allowed to hold IP information).
    pub ipv4: Option<InterfaceIpv4>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// IPv4 information.
    /// Hided if interface is not allowed to hold IP information(e.g. port of
    /// bond is not allowed to hold IP information).
    pub ipv6: Option<InterfaceIpv6>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Interface wide MPTCP flags.
    /// Nmstate will apply these flags to all valid IP addresses(both static
    /// and dynamic).
    pub mptcp: Option<MptcpConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Controller of the specified interface.
    /// Only valid for applying, `None` means no change, empty string means
    /// detach from current controller, please be advise, an error will trigger
    /// if this property conflict with ports list of bridge/bond/etc.
    /// Been always set to `None` by [crate::NetworkState::retrieve()].
    pub controller: Option<String>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    /// Whether kernel should skip check on package targeting MAC address and
    /// accept all packages, also known as promiscuous mode.
    /// Serialize and deserialize to/from `accpet-all-mac-addresses`.
    pub accept_all_mac_addresses: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Copy the MAC address from specified interface.
    /// Ignored during serializing.
    /// Deserialize from `copy-mac-from`.
    pub copy_mac_from: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "ovs-db")]
    /// Interface specific OpenvSwitch database configurations.
    pub ovsdb: Option<OvsDbIfaceConfig>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "802.1x")]
    /// IEEE 802.1X authentication configurations.
    /// Serialize and deserialize to/from `802.1x`.
    pub ieee8021x: Option<Ieee8021XConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Link Layer Discovery Protocol configurations.
    pub lldp: Option<LldpConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Ethtool configurations
    pub ethtool: Option<EthtoolConfig>,
    /// Dispatch script configurations
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dispatch: Option<DispatchConfig>,
    #[serde(skip)]
    pub controller_type: Option<InterfaceType>,
    // The interface lowest up_priority will be activated first.
    // The up_priority should be its controller's up_priority
    // plus one.
    // The 0 means top controller or no controller.
    #[serde(skip)]
    pub(crate) up_priority: u32,
    #[serde(skip)]
    pub(crate) routes: Option<Vec<RouteEntry>>,
    #[serde(flatten)]
    pub _other: serde_json::Map<String, serde_json::Value>,
}

impl BaseInterface {
    // Besides normal HashMap merging:
    //  * the IP stacks need extra care
    //  * `copy_mac_from` is skip_serializing
    //  * `permanent_mac_address` is skip_serializing
    pub(crate) fn special_merge(&mut self, desired: &Self, current: &Self) {
        if let Some(ipv4) = self.ipv4.as_mut() {
            if let (Some(d), Some(c)) =
                (desired.ipv4.as_ref(), current.ipv4.as_ref())
            {
                ipv4.special_merge(d, c);
            }
        }
        if let Some(ipv6) = self.ipv6.as_mut() {
            if let (Some(d), Some(c)) =
                (desired.ipv6.as_ref(), current.ipv6.as_ref())
            {
                ipv6.special_merge(d, c);
            }
        }
        if self.permanent_mac_address.is_none() {
            self.permanent_mac_address = current.permanent_mac_address.clone();
        }
        self.copy_mac_from = desired.copy_mac_from.clone();
    }

    fn has_controller(&self) -> bool {
        if let Some(ctrl) = self.controller.as_deref() {
            !ctrl.is_empty()
        } else {
            false
        }
    }

    /// Whether this interface can hold IP information or not.
    pub fn can_have_ip(&self) -> bool {
        (!self.has_controller())
            || self.iface_type == InterfaceType::OvsInterface
            || self.controller_type == Some(InterfaceType::Vrf)
    }

    pub(crate) fn is_up_priority_valid(&self) -> bool {
        if self.has_controller() {
            self.up_priority != 0
        } else {
            true
        }
    }

    /// Create empty [BaseInterface] with state set to [InterfaceState::Up]
    pub fn new() -> Self {
        Self {
            state: InterfaceState::Up,
            ..Default::default()
        }
    }

    pub(crate) fn clone_name_type_only(&self) -> Self {
        Self {
            name: self.name.clone(),
            iface_type: self.iface_type.clone(),
            state: InterfaceState::Up,
            ..Default::default()
        }
    }

    pub(crate) fn hide_secrets(&mut self) {
        if let Some(conf) = self.ieee8021x.as_mut() {
            conf.hide_secrets();
        }
    }

    pub(crate) fn is_ipv4_enabled(&self) -> bool {
        self.ipv4.as_ref().map(|i| i.enabled) == Some(true)
    }

    pub(crate) fn is_ipv6_enabled(&self) -> bool {
        self.ipv6.as_ref().map(|i| i.enabled) == Some(true)
    }

    pub(crate) fn sanitize(
        &mut self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        if let Some(mac) = self.mac_address.as_mut() {
            mac.make_ascii_uppercase();
        }
        // These are not for apply or verify
        self.permanent_mac_address = None;
        self.max_mtu = None;
        self.min_mtu = None;
        self.copy_mac_from = None;

        if let Some(ipv4_conf) = self.ipv4.as_mut() {
            ipv4_conf.sanitize(is_desired)?;
        }
        if let Some(ipv6_conf) = self.ipv6.as_mut() {
            ipv6_conf.sanitize(is_desired)?;
            if ipv6_conf.enabled {
                if let Some(mtu) = self.mtu {
                    if mtu < MINIMUM_IPV6_MTU {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "MTU should be >= {MINIMUM_IPV6_MTU} \
                                when IPv6 is enabled on interface {}, \
                                but got mtu: {mtu}",
                                self.name.as_str()
                            ),
                        ));
                    }
                }
            }
        }
        if let Some(lldp_conf) = self.lldp.as_mut() {
            lldp_conf.sanitize();
        }

        if !self.can_have_ip() {
            self.wait_ip = None;
        }

        if is_desired
            && self.iface_type.is_userspace()
            && self.dispatch.is_some()
        {
            return Err(NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "User space interface {}/{} is not allow to hold \
                    dispatch configurations",
                    self.name.as_str(),
                    self.iface_type,
                ),
            ));
        }

        Ok(())
    }
}

fn default_state() -> InterfaceState {
    InterfaceState::Up
}

fn default_iface_type() -> InterfaceType {
    InterfaceType::Unknown
}

impl MergedInterface {
    pub(crate) fn post_inter_ifaces_process_base_iface(
        &mut self,
    ) -> Result<(), NmstateError> {
        self.post_inter_ifaces_process_ip()?;
        self.post_inter_ifaces_process_mptcp()?;
        self.post_inter_ifaces_process_ethtool();
        self.validate_mtu()?;
        self.validate_can_have_ip()?;
        Ok(())
    }

    fn validate_mtu(&self) -> Result<(), NmstateError> {
        if let (Some(desired), Some(current)) = (
            self.desired.as_ref().map(|i| i.base_iface()),
            self.current.as_ref().map(|i| i.base_iface()),
        ) {
            if let (Some(desire_mtu), Some(min_mtu), Some(max_mtu)) =
                (desired.mtu, current.min_mtu, current.max_mtu)
            {
                if desire_mtu > max_mtu {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Desired MTU {} for interface {} \
                            is bigger than maximum allowed MTU {}",
                            desire_mtu, desired.name, max_mtu
                        ),
                    ));
                } else if desire_mtu < min_mtu {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Desired MTU {} for interface {} \
                            is smaller than minimum allowed MTU {}",
                            desire_mtu, desired.name, min_mtu
                        ),
                    ));
                }
            }
        }
        Ok(())
    }

    fn validate_can_have_ip(&mut self) -> Result<(), NmstateError> {
        if self.is_desired() && self.merged.is_up() {
            if let Some(apply_iface) = self.for_apply.as_ref() {
                let base_iface = apply_iface.base_iface();
                if !base_iface.can_have_ip()
                    && (base_iface.ipv4.as_ref().map(|ipv4| ipv4.enabled)
                        == Some(true)
                        || base_iface.ipv6.as_ref().map(|ipv6| ipv6.enabled)
                            == Some(true))
                {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Interface {} cannot have IP enabled as it is \
                            attached to a controller where IP is not allowed",
                            base_iface.name.as_str()
                        ),
                    ));
                }
            }
        }
        Ok(())
    }
}
