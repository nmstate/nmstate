// SPDX-License-Identifier: Apache-2.0

use std::net::IpAddr;

use crate::{ip::is_ipv6_unicast_link_local, InterfaceIpv4, InterfaceIpv6};

impl InterfaceIpv4 {
    pub(crate) fn update(&mut self, other: &Self) {
        if other.prop_list.contains(&"enabled") {
            self.enabled = other.enabled;
        }

        if other.prop_list.contains(&"dhcp") {
            self.dhcp = other.dhcp;
        }
        if other.prop_list.contains(&"dhcp_client_id") {
            self.dhcp_client_id = other.dhcp_client_id.clone();
        }
        if other.prop_list.contains(&"addresses") {
            self.addresses = other.addresses.clone();
        }
        if other.prop_list.contains(&"dns") {
            self.dns = other.dns.clone();
        }
        if other.prop_list.contains(&"auto_dns") {
            self.auto_dns = other.auto_dns;
        }
        if other.prop_list.contains(&"auto_gateway") {
            self.auto_gateway = other.auto_gateway;
        }
        if other.prop_list.contains(&"auto_routes") {
            self.auto_routes = other.auto_routes;
        }
        if other.prop_list.contains(&"auto_table_id") {
            self.auto_table_id = other.auto_table_id;
        }
        if other.prop_list.contains(&"allow_extra_address") {
            self.allow_extra_address = other.allow_extra_address;
        }

        for other_prop_name in &other.prop_list {
            if !self.prop_list.contains(other_prop_name) {
                self.prop_list.push(other_prop_name);
            }
        }
        self.cleanup()
    }

    // Clean up before verification
    // * Sort IP address
    // * Ignore DHCP options if DHCP disabled
    // * Ignore address if DHCP enabled
    // * Set DHCP as off if enabled and dhcp is None
    // * If `allow_extra_address: true`, remove current IP address if not found
    //   in desired.
    pub(crate) fn pre_verify_cleanup(
        &mut self,
        pre_apply_current: Option<&Self>,
        mut current: Option<&mut Self>,
    ) {
        if let Some(current) = pre_apply_current {
            self.merge_ip(current);
        }
        if let (Some(cur_ip_addrs), Some(des_ip_addrs)) = (
            current.as_mut().and_then(|c| c.addresses.as_mut()),
            self.addresses.as_ref(),
        ) {
            if self.allow_extra_address {
                cur_ip_addrs.retain(|i| {
                    // Cannot use `des_ip_addrs.contains(i)` here as
                    // InterfaceIpAddr has `mptcp_flags` which should be ignored
                    // here
                    des_ip_addrs.iter().any(|des| {
                        des.ip == i.ip && des.prefix_length == i.prefix_length
                    })
                })
            }
        }
        self.cleanup();
        if self.dhcp == Some(true) {
            self.addresses = None;
        }
        if let Some(addrs) = self.addresses.as_mut() {
            addrs.sort_unstable_by(|a, b| {
                (&a.ip, a.prefix_length).cmp(&(&b.ip, b.prefix_length))
            })
        };
        if self.dhcp != Some(true) {
            self.dhcp = Some(false);
        }
    }
}

impl InterfaceIpv6 {
    pub(crate) fn update(&mut self, other: &Self) {
        if other.prop_list.contains(&"enabled") {
            self.enabled = other.enabled;
        }
        if other.prop_list.contains(&"dhcp") {
            self.dhcp = other.dhcp;
        }
        if other.prop_list.contains(&"dhcp_duid") {
            self.dhcp_duid = other.dhcp_duid.clone();
        }
        if other.prop_list.contains(&"autoconf") {
            self.autoconf = other.autoconf;
        }
        if other.prop_list.contains(&"addr_gen_mode") {
            self.addr_gen_mode = other.addr_gen_mode.clone();
        }
        if other.prop_list.contains(&"addresses") {
            self.addresses = other.addresses.clone();
        }
        if other.prop_list.contains(&"auto_dns") {
            self.auto_dns = other.auto_dns;
        }
        if other.prop_list.contains(&"auto_gateway") {
            self.auto_gateway = other.auto_gateway;
        }
        if other.prop_list.contains(&"auto_routes") {
            self.auto_routes = other.auto_routes;
        }
        if other.prop_list.contains(&"auto_table_id") {
            self.auto_table_id = other.auto_table_id;
        }
        if other.prop_list.contains(&"dns") {
            self.dns = other.dns.clone();
        }
        if other.prop_list.contains(&"addr_gen_mode") {
            self.addr_gen_mode = other.addr_gen_mode.clone();
        }
        for other_prop_name in &other.prop_list {
            if !self.prop_list.contains(other_prop_name) {
                self.prop_list.push(other_prop_name);
            }
        }
        self.cleanup()
    }

    // Clean up before verification
    // * Remove link-local address
    // * Ignore DHCP options if DHCP disabled
    // * Ignore IP address when DHCP/autoconf enabled.
    // * Set DHCP None to Some(false)
    // * If `allow_extra_address: true`, remove current IP address if not found
    //   in desired.
    pub(crate) fn pre_verify_cleanup(
        &mut self,
        pre_apply_current: Option<&Self>,
        mut current: Option<&mut Self>,
    ) {
        if let Some(current) = pre_apply_current {
            self.merge_ip(current);
        }
        if let (Some(cur_ip_addrs), Some(des_ip_addrs)) = (
            current.as_mut().and_then(|c| c.addresses.as_mut()),
            self.addresses.as_ref(),
        ) {
            if self.allow_extra_address {
                cur_ip_addrs.retain(|i| {
                    // Cannot use `des_ip_addrs.contains(i)` here as
                    // InterfaceIpAddr has `mptcp_flags` which should be ignored
                    // here
                    des_ip_addrs.iter().any(|des| {
                        des.ip == i.ip && des.prefix_length == i.prefix_length
                    })
                })
            }
        }

        self.cleanup();
        if self.is_auto() {
            self.addresses = None;
        }
        if let Some(addrs) = self.addresses.as_mut() {
            addrs.retain(|addr| {
                if let IpAddr::V6(ip_addr) = addr.ip {
                    !is_ipv6_unicast_link_local(&ip_addr)
                } else {
                    false
                }
            })
        };
        if let Some(addrs) = self.addresses.as_mut() {
            addrs.sort_unstable_by(|a, b| {
                (&a.ip, a.prefix_length).cmp(&(&b.ip, b.prefix_length))
            })
        };
        if self.dhcp != Some(true) {
            self.dhcp = Some(false);
        }
        if self.autoconf != Some(true) {
            self.autoconf = Some(false);
        }
    }
}
