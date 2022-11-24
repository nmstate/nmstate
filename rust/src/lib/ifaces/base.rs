use log::error;
use serde::{Deserialize, Serialize};

use crate::{
    ErrorKind, InterfaceIpv4, InterfaceIpv6, InterfaceState, InterfaceType,
    NmstateError, OvsDbIfaceConfig, RouteEntry, RouteRuleEntry,
};

// TODO: Use prop_list to Serialize like InterfaceIpv4 did
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct BaseInterface {
    pub name: String,
    #[serde(skip)]
    pub prop_list: Vec<&'static str>,
    #[serde(rename = "type", default = "default_iface_type")]
    pub iface_type: InterfaceType,
    #[serde(default = "default_state")]
    pub state: InterfaceState,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mac_address: Option<String>,
    #[serde(skip)]
    pub permanent_mac_address: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mtu: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ipv4: Option<InterfaceIpv4>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ipv6: Option<InterfaceIpv6>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub controller: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub accept_all_mac_addresses: Option<bool>,
    #[serde(skip_serializing)]
    pub copy_mac_from: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "ovs-db")]
    pub ovsdb: Option<OvsDbIfaceConfig>,
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
    #[serde(skip)]
    pub(crate) rules: Option<Vec<RouteRuleEntry>>,
    #[serde(flatten)]
    pub _other: serde_json::Map<String, serde_json::Value>,
}

impl BaseInterface {
    pub(crate) fn update(&mut self, other: &BaseInterface) {
        if other.prop_list.contains(&"name") {
            self.name = other.name.clone();
        }

        if other.prop_list.contains(&"iface_type")
            && other.iface_type != InterfaceType::Unknown
        {
            self.iface_type = other.iface_type.clone();
        }
        if other.prop_list.contains(&"state") {
            self.state = other.state.clone();
        }
        if other.prop_list.contains(&"mtu") {
            self.mtu = other.mtu;
        }
        if other.prop_list.contains(&"controller") {
            self.controller = other.controller.clone();
        }
        if other.prop_list.contains(&"controller_type") {
            self.controller_type = other.controller_type.clone();
        }
        if other.prop_list.contains(&"accept_all_mac_addresses") {
            self.accept_all_mac_addresses = other.accept_all_mac_addresses;
        }
        if other.prop_list.contains(&"ovsdb") {
            self.ovsdb = other.ovsdb.clone();
        }

        if other.prop_list.contains(&"ipv4") {
            if let Some(ref other_ipv4) = other.ipv4 {
                if let Some(ref mut self_ipv4) = self.ipv4 {
                    self_ipv4.update(other_ipv4);
                } else {
                    self.ipv4 = other.ipv4.clone();
                }
            }
        }

        if other.prop_list.contains(&"ipv6") {
            if let Some(ref other_ipv6) = other.ipv6 {
                if let Some(ref mut self_ipv6) = self.ipv6 {
                    self_ipv6.update(other_ipv6);
                } else {
                    self.ipv6 = other.ipv6.clone();
                }
            }
        }
        for other_prop_name in &other.prop_list {
            if !self.prop_list.contains(other_prop_name) {
                self.prop_list.push(other_prop_name)
            }
        }
    }

    pub(crate) fn pre_edit_cleanup(&mut self) -> Result<(), NmstateError> {
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
            ipv4.pre_edit_cleanup()?
        }
        if let Some(ref mut ipv6) = self.ipv6 {
            ipv6.pre_edit_cleanup()?
        }
        Ok(())
    }

    pub(crate) fn pre_verify_cleanup(&mut self) {
        // * If cannot have IP, set ip: none
        if !self.can_have_ip() {
            self.ipv4 = None;
            self.ipv6 = None;
            self.prop_list.retain(|p| p != &"ipv4" && p != &"ipv6");
        }

        if let Some(ref mut ipv4) = self.ipv4 {
            ipv4.pre_verify_cleanup();
        }

        if let Some(ref mut ipv6) = self.ipv6 {
            ipv6.pre_verify_cleanup()
        }
        // Change all veth interface to ethernet for simpler verification
        if self.iface_type == InterfaceType::Veth {
            self.iface_type = InterfaceType::Ethernet;
        }
    }

    pub fn can_have_ip(&self) -> bool {
        self.controller.is_none()
            || self.iface_type == InterfaceType::OvsInterface
            || self.controller_type == Some(InterfaceType::Vrf)
    }

    pub(crate) fn is_up_priority_valid(&self) -> bool {
        if self.controller.is_some() {
            self.up_priority != 0
        } else {
            true
        }
    }

    pub fn new() -> Self {
        Self {
            state: InterfaceState::Up,
            ..Default::default()
        }
    }

    // TODO: Validate IP, controller and etc
    pub(crate) fn validate(&self) -> Result<(), NmstateError> {
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
}

fn default_state() -> InterfaceState {
    InterfaceState::Up
}

fn default_iface_type() -> InterfaceType {
    InterfaceType::Unknown
}
