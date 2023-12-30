// SPDX-License-Identifier: Apache-2.0

use crate::{BaseInterface, InterfaceState, InterfaceType, OvsDbIfaceConfig};

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
        // dispatch script None equal to empty
        if self.dispatch.is_none() {
            self.dispatch = Some(Default::default());
        }
        if let Some(dispatch_conf) = self.dispatch.as_mut() {
            dispatch_conf.sanitize_current_for_verify();
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
        if other.description.is_some() {
            self.description = other.description.clone();
        }
        if other.iface_type != InterfaceType::Unknown {
            self.iface_type = other.iface_type.clone();
        }
        if other.state != InterfaceState::Unknown {
            self.state = other.state;
        }
        if other.mtu.is_some() {
            self.mtu = other.mtu;
        }
        if other.min_mtu.is_some() {
            self.min_mtu = other.min_mtu;
        }
        if other.max_mtu.is_some() {
            self.max_mtu = other.max_mtu;
        }
        if other.mac_address.is_some() {
            self.mac_address = other.mac_address.clone();
        }
        if other.permanent_mac_address.is_some() {
            self.permanent_mac_address = other.permanent_mac_address.clone();
        }
        if other.controller.is_some() {
            self.controller = other.controller.clone();
        }
        if other.controller_type.is_some() {
            self.controller_type = other.controller_type.clone();
        }
        if other.accept_all_mac_addresses.is_some() {
            self.accept_all_mac_addresses = other.accept_all_mac_addresses;
        }
        if other.ovsdb.is_some() {
            self.ovsdb = other.ovsdb.clone();
        }
        if other.ieee8021x.is_some() {
            self.ieee8021x = other.ieee8021x.clone();
        }
        if other.lldp.is_some() {
            self.lldp = other.lldp.clone();
        }
        if other.ethtool.is_some() {
            self.ethtool = other.ethtool.clone();
        }
        if other.mptcp.is_some() {
            self.mptcp = other.mptcp.clone();
        }
        if other.wait_ip.is_some() {
            self.wait_ip = other.wait_ip;
        }

        if other.ipv4.is_some() {
            if let Some(ref other_ipv4) = other.ipv4 {
                if let Some(ref mut self_ipv4) = self.ipv4 {
                    self_ipv4.update(other_ipv4);
                } else {
                    self.ipv4 = other.ipv4.clone();
                }
            }
        }

        if other.ipv6.is_some() {
            if let Some(ref other_ipv6) = other.ipv6 {
                if let Some(ref mut self_ipv6) = self.ipv6 {
                    self_ipv6.update(other_ipv6);
                } else {
                    self.ipv6 = other.ipv6.clone();
                }
            }
        }
        if other.mptcp.is_some() {
            self.mptcp = other.mptcp.clone();
        }
        if other.identifier.is_some() {
            self.identifier = other.identifier;
        }
        if other.profile_name.is_some() {
            self.profile_name = other.profile_name.clone();
        }
        if other.dispatch.is_some() {
            self.dispatch = other.dispatch.clone();
        }
    }
}
