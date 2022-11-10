use log::error;
use serde::{Deserialize, Serialize};

use crate::{
    ip::validate_wait_ip,
    mptcp::{mptcp_pre_edit_cleanup, validate_mptcp},
    ErrorKind, EthtoolConfig, Ieee8021XConfig, InterfaceIpv4, InterfaceIpv6,
    InterfaceState, InterfaceType, LldpConfig, MptcpConfig, NmstateError,
    OvsDbIfaceConfig, RouteEntry, RouteRuleEntry, WaitIp,
};

// TODO: Use prop_list to Serialize like InterfaceIpv4 did
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
/// Information shared among all interface types
pub struct BaseInterface {
    /// Interface name
    pub name: String,
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
    #[serde(skip_serializing_if = "Option::is_none")]
    /// MAC address in the format: upper case hex string separated by `:` on
    /// every two characters. Case insensitive when applying.
    /// Serialize and deserialize to/from `mac-address`.
    pub mac_address: Option<String>,
    #[serde(skip)]
    /// MAC address never change after reboots(normally stored in firmware of
    /// network interface). Using the same format as `mac_address` property.
    /// Ignored during apply.
    /// TODO: expose it.
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
    // None here mean no change, empty string mean detach from controller.
    /// TODO: Internal only. Hide it.
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
    #[serde(skip_serializing)]
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
    #[serde(skip)]
    /// TODO: internal use, hide it.
    pub controller_type: Option<InterfaceType>,
    // The interface lowest up_priority will be activated first.
    // The up_priority should be its controller's up_priority
    // plus one.
    // The 0 means top controller or no controller.
    #[serde(skip)]
    pub(crate) up_priority: u32,
    #[serde(skip)]
    pub(crate) routes: Option<Vec<RouteEntry>>,
    #[serde(skip)]
    pub(crate) rules: Option<Vec<RouteRuleEntry>>,
    #[serde(flatten)]
    pub _other: serde_json::Map<String, serde_json::Value>,
}

impl BaseInterface {
    pub(crate) fn pre_edit_cleanup(
        &mut self,
        current: Option<&Self>,
    ) -> Result<(), NmstateError> {
        self.validate_mtu(current)?;
        validate_mptcp(self)?;
        validate_wait_ip(self)?;

        // Do not allow changing min_mtu and max_mtu
        self.max_mtu = None;
        self.min_mtu = None;
        if !self.can_have_ip()
            && (self.ipv4.as_ref().map(|ipv4| ipv4.enabled) == Some(true)
                || self.ipv6.as_ref().map(|ipv6| ipv6.enabled) == Some(true))
        {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                format!(
                    "Interface {} cannot have IP enabled as it is \
                    attached to a controller",
                    self.name
                ),
            );
            error!("{}", e);
            return Err(e);
        }

        if let Some(ref mut ipv4) = self.ipv4 {
            ipv4.pre_edit_cleanup(current.and_then(|i| i.ipv4.as_ref()));
        }
        if let Some(ref mut ipv6) = self.ipv6 {
            ipv6.pre_edit_cleanup(current.and_then(|i| i.ipv6.as_ref()));
        }
        if let Some(ref mut ethtool_conf) = self.ethtool {
            ethtool_conf.pre_edit_cleanup();
        }

        mptcp_pre_edit_cleanup(self);

        Ok(())
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

    fn validate_mtu(&self, current: Option<&Self>) -> Result<(), NmstateError> {
        if let (Some(desire_mtu), Some(min_mtu), Some(max_mtu)) = (
            self.mtu,
            current.and_then(|c| c.min_mtu),
            current.and_then(|c| c.max_mtu),
        ) {
            if desire_mtu > max_mtu {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Desired MTU {} for interface {} \
                        is bigger than maximum allowed MTU {}",
                        desire_mtu, self.name, max_mtu
                    ),
                ));
            } else if desire_mtu < min_mtu {
                return Err(NmstateError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Desired MTU {} for interface {} \
                        is smaller than minimum allowed MTU {}",
                        desire_mtu, self.name, min_mtu
                    ),
                ));
            }
        }
        Ok(())
    }

    pub(crate) fn clone_name_type_only(&self) -> Self {
        Self {
            name: self.name.clone(),
            iface_type: self.iface_type.clone(),
            state: InterfaceState::Up,
            ..Default::default()
        }
    }

    pub(crate) fn copy_ip_config_if_none(&mut self, current: &Self) {
        if self.ipv4.is_none() {
            self.ipv4 = current.ipv4.clone();
        }
        if self.ipv6.is_none() {
            self.ipv6 = current.ipv6.clone();
        }
    }

    pub(crate) fn hide_secrets(&mut self) {
        if let Some(conf) = self.ieee8021x.as_mut() {
            conf.hide_secrets();
        }
    }
}

fn default_state() -> InterfaceState {
    InterfaceState::Up
}

fn default_iface_type() -> InterfaceType {
    InterfaceType::Unknown
}
