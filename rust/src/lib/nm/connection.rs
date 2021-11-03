use std::collections::{hash_map::Entry, HashMap};

use nm_dbus::{NmApi, NmConnection, NmSettingConnection};

use crate::{
    nm::bridge::linux_bridge_conf_to_nm,
    nm::ip::{iface_ipv4_to_nm, iface_ipv6_to_nm},
    nm::profile::get_exist_profile,
    ErrorKind, Interface, InterfaceIpv4, InterfaceIpv6, InterfaceType,
    NetworkState, NmstateError,
};

pub(crate) fn nm_gen_conf(
    net_state: &NetworkState,
) -> Result<Vec<String>, NmstateError> {
    let mut ret = Vec::new();
    let ifaces = net_state.interfaces.to_vec();
    for iface in &ifaces {
        let (_, nm_conn) = iface_to_nm_connection(iface, &[], &[])?;
        ret.push(match nm_conn.to_keyfile() {
            Ok(s) => s,
            Err(e) => {
                return Err(NmstateError::new(
                    ErrorKind::PluginFailure,
                    format!(
                        "Bug in NM plugin, failed to generate configure: {}",
                        e
                    ),
                ));
            }
        })
    }
    Ok(ret)
}

pub(crate) fn iface_to_nm_connection(
    iface: &Interface,
    exist_nm_conns: &[NmConnection],
    nm_ac_uuids: &[&str],
) -> Result<(String, NmConnection), NmstateError> {
    let base_iface = iface.base_iface();
    let exist_nm_conn = get_exist_profile(
        exist_nm_conns,
        &base_iface.name,
        &base_iface.iface_type,
        nm_ac_uuids,
    );

    let uuid = if let Some(exist_nm_conn) = exist_nm_conn {
        if let Some(exist_uuid) = exist_nm_conn.uuid() {
            exist_uuid.to_string()
        } else {
            NmApi::uuid_gen()
        }
    } else {
        NmApi::uuid_gen()
    };
    let mut nm_conn_set = NmSettingConnection {
        id: Some(base_iface.name.clone()),
        uuid: Some(uuid.clone()),
        iface_type: Some(iface_type_to_nm(&base_iface.iface_type)?),
        iface_name: Some(base_iface.name.clone()),
        autoconnect: Some(true),
        autoconnect_ports: if iface.is_controller() {
            Some(true)
        } else {
            None
        },
        ..Default::default()
    };
    if let Some(ctrl_name) = &base_iface.controller {
        if let Some(ctrl_type) = &base_iface.controller_type {
            nm_conn_set.controller = Some(ctrl_name.to_string());
            nm_conn_set.controller_type = Some(iface_type_to_nm(ctrl_type)?);
        }
    }
    let mut nm_conn = NmConnection::new();
    nm_conn.connection = Some(nm_conn_set);
    if base_iface.can_have_ip() {
        if let Some(iface_ip) = &base_iface.ipv4 {
            nm_conn.ipv4 = Some(iface_ipv4_to_nm(iface_ip)?);
        } else {
            nm_conn.ipv4 = Some(iface_ipv4_to_nm(&InterfaceIpv4 {
                enabled: false,
                ..Default::default()
            })?);
        }
        if let Some(iface_ip) = &base_iface.ipv6 {
            nm_conn.ipv6 = Some(iface_ipv6_to_nm(iface_ip)?);
        } else {
            nm_conn.ipv6 = Some(iface_ipv6_to_nm(&InterfaceIpv6 {
                enabled: false,
                ..Default::default()
            })?);
        }
    }
    if let Interface::LinuxBridge(br_iface) = iface {
        if let Some(br_conf) = &br_iface.bridge {
            nm_conn.bridge = Some(linux_bridge_conf_to_nm(br_conf)?);
        }
    }
    Ok((uuid, nm_conn))
}

pub(crate) fn iface_type_to_nm(
    iface_type: &InterfaceType,
) -> Result<String, NmstateError> {
    match iface_type {
        InterfaceType::LinuxBridge => Ok("bridge".into()),
        InterfaceType::Ethernet => Ok("802-3-ethernet".into()),
        _ => Err(NmstateError::new(
            ErrorKind::NotImplementedError,
            format!("Does not support iface type: {:?} yet", iface_type),
        )),
    }
}

pub(crate) fn create_index_for_nm_conns(
    nm_conns: &[NmConnection],
) -> HashMap<(String, String), Vec<&NmConnection>> {
    let mut ret: HashMap<(String, String), Vec<&NmConnection>> = HashMap::new();
    for nm_conn in nm_conns {
        if let Some(iface_name) = nm_conn.iface_name() {
            if let Some(nm_iface_type) = nm_conn.iface_type() {
                match ret
                    .entry((iface_name.to_string(), nm_iface_type.to_string()))
                {
                    Entry::Occupied(o) => {
                        o.into_mut().push(nm_conn);
                    }
                    Entry::Vacant(v) => {
                        v.insert(vec![nm_conn]);
                    }
                };
            }
        }
    }
    ret
}
