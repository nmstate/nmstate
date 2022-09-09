use crate::{InterfaceIpAddr, InterfaceIpv4, InterfaceIpv6};

pub(crate) fn np_ipv4_to_nmstate(
    np_iface: &nispor::Iface,
) -> Option<InterfaceIpv4> {
    if let Some(np_ip) = &np_iface.ipv4 {
        let mut ip = InterfaceIpv4::default();
        ip.prop_list.push("enabled");
        ip.prop_list.push("addresses");
        if !np_ip.addresses.is_empty() {
            ip.enabled = true;
        }
        for np_addr in &np_ip.addresses {
            if np_addr.valid_lft != "forever" {
                ip.dhcp = true;
                ip.prop_list.push("dhcp");
            }
            ip.addresses.push(InterfaceIpAddr {
                ip: np_addr.address.clone(),
                prefix_length: np_addr.prefix_len,
            });
        }
        Some(ip)
    } else {
        // IP might just disabled
        if np_iface.controller.is_none() {
            Some(InterfaceIpv4 {
                enabled: false,
                prop_list: vec!["enabled"],
                ..Default::default()
            })
        } else {
            None
        }
    }
}

pub(crate) fn np_ipv6_to_nmstate(
    np_iface: &nispor::Iface,
) -> Option<InterfaceIpv6> {
    if let Some(np_ip) = &np_iface.ipv6 {
        let mut ip = InterfaceIpv6::default();
        ip.prop_list.push("enabled");
        ip.prop_list.push("addresses");
        if !np_ip.addresses.is_empty() {
            ip.enabled = true;
        }
        for np_addr in &np_ip.addresses {
            if np_addr.valid_lft != "forever" {
                ip.autoconf = true;
                ip.prop_list.push("autoconf");
            }
            ip.addresses.push(InterfaceIpAddr {
                ip: np_addr.address.clone(),
                prefix_length: np_addr.prefix_len,
            });
        }
        Some(ip)
    } else {
        // IP might just disabled
        if np_iface.controller.is_none() {
            Some(InterfaceIpv6 {
                enabled: false,
                prop_list: vec!["enabled"],
                ..Default::default()
            })
        } else {
            None
        }
    }
}

pub(crate) fn nmstate_ipv4_to_np(
    nms_ipv4: Option<&InterfaceIpv4>,
) -> nispor::IpConf {
    let mut np_ip_conf = nispor::IpConf::default();
    if let Some(nms_ipv4) = nms_ipv4 {
        for nms_addr in &nms_ipv4.addresses {
            np_ip_conf.addresses.push({
                let mut ip_conf = nispor::IpAddrConf::default();
                ip_conf.address = nms_addr.ip.to_string();
                ip_conf.prefix_len = nms_addr.prefix_length as u8;
                ip_conf
            });
        }
    }
    np_ip_conf
}

pub(crate) fn nmstate_ipv6_to_np(
    nms_ipv6: Option<&InterfaceIpv6>,
) -> nispor::IpConf {
    let mut np_ip_conf = nispor::IpConf::default();
    if let Some(nms_ipv6) = nms_ipv6 {
        for nms_addr in &nms_ipv6.addresses {
            np_ip_conf.addresses.push({
                let mut ip_conf = nispor::IpAddrConf::default();
                ip_conf.address = nms_addr.ip.to_string();
                ip_conf.prefix_len = nms_addr.prefix_length as u8;
                ip_conf
            });
        }
    }
    np_ip_conf
}
