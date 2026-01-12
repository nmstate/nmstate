// SPDX-License-Identifier: Apache-2.0

use std::str::FromStr;

use super::super::{
    NmConnectionMatcher,
    nm_dbus::{NmActiveConnection, NmIfaceType, NmSettingVpn},
    show::fill_iface_by_nm_conn_data,
};
use crate::{
    Interface, InterfaceState, InterfaceType, IpsecInterface,
    LibreswanAddressFamily, LibreswanConfig, LibreswanConnectionType,
    NmstateError,
};

pub(crate) fn get_supported_vpn_ifaces(
    conn_matcher: &NmConnectionMatcher,
) -> Result<Vec<Interface>, NmstateError> {
    let mut ret = Vec::new();
    for nm_conn in conn_matcher.saved_iter().filter(|nm_conn| {
        nm_conn
            .uuid()
            .as_ref()
            .map(|uuid| conn_matcher.is_uuid_activated(uuid))
            .unwrap()
            && nm_conn.iface_type() == Some(&NmIfaceType::Vpn)
    }) {
        let nm_ac = if let Some(nm_ac) = nm_conn
            .uuid()
            .and_then(|uuid| conn_matcher.get_nm_ac_by_uuid(uuid))
        {
            nm_ac
        } else {
            continue;
        };
        if let Some(nm_set_vpn) = nm_conn.vpn.as_ref()
            && nm_set_vpn.service_type.as_deref()
                == Some(NmSettingVpn::SERVICE_TYPE_LIBRESWAN)
        {
            let name = match nm_conn.id() {
                Some(n) => n.to_string(),
                None => continue,
            };
            // taking profile name as interface name of VPN.
            let mut iface = IpsecInterface::new();
            iface.base.iface_type = InterfaceType::Ipsec;
            // We are solely depend on NetworkManager reporting IPSec
            // connection status, hence use NmActiveConnection.state
            // for interface.state
            iface.base.state =
                if nm_ac.state == NmActiveConnection::STATE_ACTIVATED {
                    InterfaceState::Up
                } else {
                    InterfaceState::Down
                };
            iface.base.name = name;
            iface.libreswan = Some(get_libreswan_conf(nm_set_vpn));
            let mut iface = Interface::Ipsec(Box::new(iface));
            fill_iface_by_nm_conn_data(&mut iface, None, Some(nm_conn), None);
            ret.push(iface);
        }
    }
    Ok(ret)
}

fn get_libreswan_conf(nm_set_vpn: &NmSettingVpn) -> LibreswanConfig {
    let mut ret = LibreswanConfig::new();
    if let Some(data) = nm_set_vpn.data.as_ref() {
        if let Some(v) = data.get("right") {
            ret.right.clone_from(v);
        }
        ret.nm_auto_defaults =
            data.get("nm-auto-defaults").map(|s| s.as_str()) != Some("no");
        ret.rightid = data.get("rightid").cloned();
        ret.rightrsasigkey = data.get("rightrsasigkey").cloned();
        ret.rightcert = data.get("rightcert").cloned();
        ret.left = data.get("left").cloned();
        ret.leftid = data.get("leftid").cloned();
        ret.leftcert = data.get("leftcert").cloned();
        ret.leftrsasigkey = data.get("leftrsasigkey").cloned();
        ret.ikev2 = data.get("ikev2").cloned();
        ret.ikelifetime = data.get("ikelifetime").cloned();
        ret.salifetime = data.get("salifetime").cloned();
        ret.ike = data.get("ike").cloned();
        ret.esp = data.get("esp").cloned();
        ret.dpddelay = data.get("dpddelay").and_then(|d| u64::from_str(d).ok());
        ret.dpdtimeout =
            data.get("dpdtimeout").and_then(|d| u64::from_str(d).ok());
        ret.dpdaction = data.get("dpdaction").cloned();
        ret.ipsec_interface = data.get("ipsec-interface").cloned();
        ret.authby = data.get("authby").cloned();
        ret.leftmodecfgclient =
            data.get("leftmodecfgclient").map(|s| s == "yes");
        ret.rightsubnet = data.get("rightsubnet").cloned();
        ret.leftsubnet = data.get("leftsubnet").cloned();
        ret.kind = data.get("type").and_then(|s| match s.as_str() {
            "tunnel" => Some(LibreswanConnectionType::Tunnel),
            "transport" => Some(LibreswanConnectionType::Transport),
            _ => {
                log::warn!("Unknown NetworkManager libreswan type {s}");
                None
            }
        });
        ret.hostaddrfamily = data
            .get("hostaddrfamily")
            .and_then(|s| nm_libreswan_addr_family_to_nmstate(s));
        ret.clientaddrfamily = data
            .get("clientaddrfamily")
            .and_then(|s| nm_libreswan_addr_family_to_nmstate(s));
        ret.require_id_on_certificate =
            data.get("require-id-on-certificate").map(|s| s == "yes");
        ret.leftsendcert = data.get("leftsendcert").cloned();
        ret.rightca = data.get("rightca").cloned();
        ret.leftprotoport = data.get("leftprotoport").cloned();
        ret.rightprotoport = data.get("rightprotoport").cloned();
    }
    if let Some(secrets) = nm_set_vpn.secrets.as_ref() {
        ret.psk = secrets.get("pskvalue").cloned();
    }
    ret
}

fn nm_libreswan_addr_family_to_nmstate(
    family: &str,
) -> Option<LibreswanAddressFamily> {
    match family {
        "ipv4" => Some(LibreswanAddressFamily::Ipv4),
        "ipv6" => Some(LibreswanAddressFamily::Ipv6),
        _ => {
            log::warn!(
                "Unknown address family {family} from libreswan VPN data"
            );
            None
        }
    }
}
