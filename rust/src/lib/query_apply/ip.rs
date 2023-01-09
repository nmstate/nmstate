// SPDX-License-Identifier: Apache-2.0

use crate::{Interface, InterfaceIpv4, InterfaceIpv6};

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
        if other.prop_list.contains(&"rules") {
            self.rules = other.rules.clone();
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
        if other.prop_list.contains(&"auto_route_metric") {
            self.auto_route_metric = other.auto_route_metric;
        }

        for other_prop_name in &other.prop_list {
            if !self.prop_list.contains(other_prop_name) {
                self.prop_list.push(other_prop_name);
            }
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
        if other.prop_list.contains(&"rules") {
            self.rules = other.rules.clone();
        }
        if other.prop_list.contains(&"addr_gen_mode") {
            self.addr_gen_mode = other.addr_gen_mode.clone();
        }
        if other.prop_list.contains(&"auto_route_metric") {
            self.auto_route_metric = other.auto_route_metric;
        }
        for other_prop_name in &other.prop_list {
            if !self.prop_list.contains(other_prop_name) {
                self.prop_list.push(other_prop_name);
            }
        }
    }
}

impl Interface {
    // * If `allow_extra_address: true`, remove current IP address if not found
    //   in desired.
    pub(crate) fn process_allow_extra_address(&self, current: &mut Self) {
        if let (Some(des_ip), Some(cur_ip)) = (
            self.base_iface().ipv4.as_ref(),
            current.base_iface_mut().ipv4.as_mut(),
        ) {
            if let (Some(des_ip_addrs), Some(cur_ip_addrs)) =
                (des_ip.addresses.as_ref(), cur_ip.addresses.as_mut())
            {
                if des_ip.allow_extra_address {
                    cur_ip_addrs.retain(|i| des_ip_addrs.contains(i))
                }
            }
        }
        if let (Some(des_ip), Some(cur_ip)) = (
            self.base_iface().ipv6.as_ref(),
            current.base_iface_mut().ipv6.as_mut(),
        ) {
            if let (Some(des_ip_addrs), Some(cur_ip_addrs)) =
                (des_ip.addresses.as_ref(), cur_ip.addresses.as_mut())
            {
                if des_ip.allow_extra_address {
                    cur_ip_addrs.retain(|i| des_ip_addrs.contains(i))
                }
            }
        }
    }
}
