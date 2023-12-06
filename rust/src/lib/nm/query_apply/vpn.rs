// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{
    Interface, InterfaceType, IpsecInterface, LibreswanConfig, NmstateError,
};

use super::super::{
    nm_dbus::{NmActiveConnection, NmConnection, NmSettingVpn},
    show::nm_conn_to_base_iface,
};

pub(crate) fn get_supported_vpn_ifaces(
    nm_saved_conn_uuid_index: &HashMap<&str, &NmConnection>,
    nm_acs: &[NmActiveConnection],
) -> Result<Vec<Interface>, NmstateError> {
    let mut ret = Vec::new();
    for nm_conn in nm_acs.iter().filter_map(|nm_ac| {
        if nm_ac.iface_type == "vpn" {
            nm_saved_conn_uuid_index.get(nm_ac.uuid.as_str())
        } else {
            None
        }
    }) {
        if let Some(nm_set_vpn) = nm_conn.vpn.as_ref() {
            if nm_set_vpn.service_type.as_deref()
                == Some(NmSettingVpn::SERVICE_TYPE_LIBRESWAN)
            {
                if let Some(mut base_iface) =
                    nm_conn_to_base_iface(None, nm_conn, None, None)
                {
                    let mut iface = IpsecInterface::new();
                    base_iface.iface_type = InterfaceType::Ipsec;
                    iface.base = base_iface;
                    iface.libreswan = Some(get_libreswan_conf(nm_set_vpn));
                    ret.push(Interface::Ipsec(iface));
                }
            }
        }
    }
    Ok(ret)
}

fn get_libreswan_conf(nm_set_vpn: &NmSettingVpn) -> LibreswanConfig {
    let mut ret = LibreswanConfig::new();
    if let Some(data) = nm_set_vpn.data.as_ref() {
        if let Some(v) = data.get("right") {
            ret.right = v.clone();
        }
        ret.rightid = data.get("rightid").cloned();
        ret.rightrsasigkey = data.get("rightrsasigkey").cloned();
        ret.left = data.get("left").cloned();
        ret.leftid = data.get("leftid").cloned();
        ret.leftcert = data.get("leftcert").cloned();
        ret.leftrsasigkey = data.get("leftrsasigkey").cloned();
        ret.ikev2 = data.get("ikev2").cloned();
        ret.ikelifetime = data.get("ikelifetime").cloned();
        ret.salifetime = data.get("salifetime").cloned();
        ret.ike = data.get("ike").cloned();
        ret.esp = data.get("esp").cloned();
    }
    if let Some(secrets) = nm_set_vpn.secrets.as_ref() {
        ret.psk = secrets.get("pskvalue").cloned();
    }
    ret
}

pub(crate) fn get_match_ipsec_nm_conn<'a>(
    iface_name: &str,
    all_nm_conns: &'a [NmConnection],
) -> Vec<&'a NmConnection> {
    all_nm_conns
        .iter()
        .filter(|c| c.iface_type() == Some("vpn") && c.id() == Some(iface_name))
        .collect()
}
