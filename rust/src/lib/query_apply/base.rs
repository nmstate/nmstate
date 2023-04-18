// SPDX-License-Identifier: Apache-2.0

use crate::{BaseInterface, InterfaceType, OvsDbIfaceConfig};

impl BaseInterface {
    pub(crate) fn sanitize_current_for_verify(&mut self) {
        if self.controller.is_none() {
            self.controller = Some(String::new());
        }
        if let Some(mptcp_conf) = self.mptcp.as_mut() {
            mptcp_conf.sanitize_current_for_verify();
        }
        if let Some(ipv4_conf) = self.ipv4.as_mut() {
            ipv4_conf.sanitize_current_for_verify();
        }
        if let Some(ipv6_conf) = self.ipv6.as_mut() {
            ipv6_conf.sanitize_current_for_verify();
        }
        // ovsdb None equal to empty
        if self.ovsdb.is_none() {
            self.ovsdb = Some(OvsDbIfaceConfig::new_empty());
        }
    }

    pub(crate) fn sanitize_desired_for_verify(&mut self) {
        if let Some(ipv4_conf) = self.ipv4.as_mut() {
            ipv4_conf.sanitize_desired_for_verify();
        }
        if let Some(ipv6_conf) = self.ipv6.as_mut() {
            ipv6_conf.sanitize_desired_for_verify();
        }
        if let Some(mptcp_conf) = self.mptcp.as_mut() {
            mptcp_conf.sanitize_desired_for_verify();
        }
        // When `profile_name` is the same with iface name, it was hidden during
        // query, we should ignore it during verify
        if self.profile_name.as_deref() == Some(self.name.as_str()) {
            self.profile_name = None;
        }
    }

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
            self.state = other.state;
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
        if other.prop_list.contains(&"mac_address") {
            self.mac_address = other.mac_address.clone();
        }
        if other.prop_list.contains(&"permanent_mac_address") {
            self.permanent_mac_address = other.permanent_mac_address.clone();
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
        if other.prop_list.contains(&"identifier") {
            self.identifier = other.identifier;
        }
        if other.prop_list.contains(&"profile_name") {
            self.profile_name = other.profile_name.clone();
        }
        for other_prop_name in &other.prop_list {
            if !self.prop_list.contains(other_prop_name) {
                self.prop_list.push(other_prop_name)
            }
        }
    }
}
