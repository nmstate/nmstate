// SPDX-License-Identifier: Apache-2.0

use crate::{Interface, InterfaceIpv4, InterfaceIpv6};

impl InterfaceIpv4 {
    // Sort addresses and dedup
    pub(crate) fn sanitize_current_for_verify(&mut self) {
        if let Some(addrs) = self.addresses.as_mut() {
            addrs.sort_unstable();
            addrs.dedup();
        }
        if self.dhcp_custom_hostname.is_none() {
            self.dhcp_custom_hostname = Some(String::new());
        }

        // No IP address means empty.
        if self.addresses.is_none() {
            self.addresses = Some(Vec::new());
        }

        // No DHCP means off
        if self.dhcp.is_none() {
            self.dhcp = Some(false);
        }
    }

    // Sort addresses and dedup
    pub(crate) fn sanitize_desired_for_verify(&mut self) {
        if let Some(addrs) = self.addresses.as_mut() {
            if addrs.is_empty() {
                // For empty address, we do not care about ip stack enabled or
                // false as it might varied depend on whether have route on it
                self.enabled_defined = false;
            } else {
                addrs.sort_unstable();
                addrs.dedup();
            }
        }
    }
    pub(crate) fn update(&mut self, other: &Self) {
        if other.enabled_defined {
            self.enabled = other.enabled;
        }

        if other.dhcp.is_some() {
            self.dhcp = other.dhcp;
        }
        if other.dhcp_client_id.is_some() {
            self.dhcp_client_id.clone_from(&other.dhcp_client_id);
        }
        if other.addresses.is_some() {
            self.addresses.clone_from(&other.addresses);
        }
        if other.dns.is_some() {
            self.dns.clone_from(&other.dns);
        }
        if other.rules.is_some() {
            self.rules.clone_from(&other.rules);
        }
        if other.auto_dns.is_some() {
            self.auto_dns = other.auto_dns;
        }
        if other.auto_gateway.is_some() {
            self.auto_gateway = other.auto_gateway;
        }
        if other.auto_routes.is_some() {
            self.auto_routes = other.auto_routes;
        }
        if other.auto_table_id.is_some() {
            self.auto_table_id = other.auto_table_id;
        }
        if other.allow_extra_address.is_some() {
            self.allow_extra_address = other.allow_extra_address;
        }
        if other.auto_route_metric.is_some() {
            self.auto_route_metric = other.auto_route_metric;
        }
        if other.dhcp_send_hostname.is_some() {
            self.dhcp_send_hostname = other.dhcp_send_hostname;
        }
        if other.dhcp_custom_hostname.is_some() {
            self.dhcp_custom_hostname
                .clone_from(&other.dhcp_custom_hostname);
        }
    }
}

impl InterfaceIpv6 {
    // Sort addresses and dedup
    pub(crate) fn sanitize_current_for_verify(&mut self) {
        if let Some(addrs) = self.addresses.as_mut() {
            addrs.sort_unstable();
            addrs.dedup();
        }

        // None IPv6 token should be treat as "::"
        if self.token.is_none() {
            self.token = Some("::".to_string());
        }
        if self.dhcp_custom_hostname.is_none() {
            self.dhcp_custom_hostname = Some(String::new());
        }

        // No IP address means empty.
        if self.enabled && self.addresses.is_none() {
            self.addresses = Some(Vec::new());
        }

        // No DHCP means off
        if self.enabled && self.dhcp.is_none() {
            self.dhcp = Some(false);
        }

        // No autoconf means off
        if self.enabled && self.autoconf.is_none() {
            self.autoconf = Some(false);
        }
    }

    // Sort addresses and dedup
    pub(crate) fn sanitize_desired_for_verify(&mut self) {
        if let Some(addrs) = self.addresses.as_mut() {
            addrs.sort_unstable();
            addrs.dedup();
        }
    }
    pub(crate) fn update(&mut self, other: &Self) {
        if other.enabled_defined {
            self.enabled = other.enabled;
        }
        if other.dhcp.is_some() {
            self.dhcp = other.dhcp;
        }
        if other.dhcp_duid.is_some() {
            self.dhcp_duid.clone_from(&other.dhcp_duid);
        }
        if other.autoconf.is_some() {
            self.autoconf = other.autoconf;
        }
        if other.addr_gen_mode.is_some() {
            self.addr_gen_mode.clone_from(&other.addr_gen_mode);
        }
        if other.addresses.is_some() {
            self.addresses.clone_from(&other.addresses);
        }
        if other.auto_dns.is_some() {
            self.auto_dns = other.auto_dns;
        }
        if other.auto_gateway.is_some() {
            self.auto_gateway = other.auto_gateway;
        }
        if other.auto_routes.is_some() {
            self.auto_routes = other.auto_routes;
        }
        if other.auto_table_id.is_some() {
            self.auto_table_id = other.auto_table_id;
        }
        if other.dns.is_some() {
            self.dns.clone_from(&other.dns);
        }
        if other.rules.is_some() {
            self.rules.clone_from(&other.rules);
        }
        if other.addr_gen_mode.is_some() {
            self.addr_gen_mode.clone_from(&other.addr_gen_mode);
        }
        if other.auto_route_metric.is_some() {
            self.auto_route_metric = other.auto_route_metric;
        }
        if other.token.is_some() {
            self.token.clone_from(&other.token);
        }
        if other.dhcp_send_hostname.is_some() {
            self.dhcp_send_hostname = other.dhcp_send_hostname;
        }
        if other.dhcp_custom_hostname.is_some() {
            self.dhcp_custom_hostname
                .clone_from(&other.dhcp_custom_hostname);
        }
    }
}

impl Interface {
    // * If `allow_extra_address: true`, remove current IP address if not found
    //   in desired.
    pub(crate) fn process_allow_extra_address(&mut self, current: &mut Self) {
        if let (Some(des_ip), Some(cur_ip)) = (
            self.base_iface_mut().ipv4.as_mut(),
            current.base_iface_mut().ipv4.as_mut(),
        ) {
            if let (Some(des_ip_addrs), Some(cur_ip_addrs)) =
                (des_ip.addresses.as_ref(), cur_ip.addresses.as_mut())
            {
                if des_ip.allow_extra_address != Some(false) {
                    cur_ip_addrs.retain(|i| des_ip_addrs.contains(i))
                }
                // Remove allow_extra_address as current does not have it
                des_ip.allow_extra_address = None
            }
        }
        if let (Some(des_ip), Some(cur_ip)) = (
            self.base_iface_mut().ipv6.as_mut(),
            current.base_iface_mut().ipv6.as_mut(),
        ) {
            if let (Some(des_ip_addrs), Some(cur_ip_addrs)) =
                (des_ip.addresses.as_ref(), cur_ip.addresses.as_mut())
            {
                if des_ip.allow_extra_address != Some(false) {
                    cur_ip_addrs.retain(|i| des_ip_addrs.contains(i))
                }
                // Remove allow_extra_address as current does not have it
                des_ip.allow_extra_address = None
            }
        }
    }
}
