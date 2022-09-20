// SPDX-License-Identifier: Apache-2.0

use crate::{
    query_apply::mptcp::mptcp_pre_verify_cleanup, BaseInterface, InterfaceType,
};

impl BaseInterface {
    pub(crate) fn update(&mut self, other: &BaseInterface) {
        if other.prop_list.contains(&"name") {
            self.name = other.name.clone();
        }
        if other.prop_list.contains(&"description") {
            self.description = other.description.clone();
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
        if other.prop_list.contains(&"min_mtu") {
            self.min_mtu = other.min_mtu;
        }
        if other.prop_list.contains(&"max_mtu") {
            self.max_mtu = other.max_mtu;
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
        if other.prop_list.contains(&"ieee8021x") {
            self.ieee8021x = other.ieee8021x.clone();
        }
        if other.prop_list.contains(&"lldp") {
            self.lldp = other.lldp.clone();
        }
        if other.prop_list.contains(&"ethtool") {
            self.ethtool = other.ethtool.clone();
        }
        if other.prop_list.contains(&"mptcp") {
            self.mptcp = other.mptcp.clone();
        }
        if other.prop_list.contains(&"wait_ip") {
            self.wait_ip = other.wait_ip;
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
        if other.prop_list.contains(&"mptcp") {
            self.mptcp = other.mptcp.clone();
        }
        for other_prop_name in &other.prop_list {
            if !self.prop_list.contains(other_prop_name) {
                self.prop_list.push(other_prop_name)
            }
        }
    }

    pub(crate) fn pre_verify_cleanup(
        &mut self,
        pre_apply_current: Option<&Self>,
    ) {
        // Ignore min_mtu and max_mtu as they are not changeable
        self.min_mtu = None;
        self.max_mtu = None;
        // * If cannot have IP, set ip: none
        if !self.can_have_ip() {
            self.ipv4 = None;
            self.ipv6 = None;
            self.prop_list.retain(|p| p != &"ipv4" && p != &"ipv6");
        }

        if let Some(ref mut ipv4) = self.ipv4 {
            ipv4.pre_verify_cleanup(
                pre_apply_current.and_then(|i| i.ipv4.as_ref()),
            );
        }

        if let Some(ref mut ipv6) = self.ipv6 {
            ipv6.pre_verify_cleanup(
                pre_apply_current.and_then(|i| i.ipv6.as_ref()),
            );
        }
        // Change all veth interface to ethernet for simpler verification
        if self.iface_type == InterfaceType::Veth {
            self.iface_type = InterfaceType::Ethernet;
        }

        if let Some(mac_address) = &self.mac_address {
            self.mac_address = Some(mac_address.to_uppercase());
        }
        if let Some(lldp_conf) = self.lldp.as_mut() {
            lldp_conf.pre_verify_cleanup();
        }
        if let Some(ethtool_conf) = self.ethtool.as_mut() {
            ethtool_conf.pre_verify_cleanup();
        }
        mptcp_pre_verify_cleanup(self);
    }
}
