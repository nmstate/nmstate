use std::collections::{hash_map::Entry, HashMap};

use nm_dbus::{NmApi, NmConnection, NmSettingConnection, NmSettingWired};

use crate::{
    nm::bridge::linux_bridge_conf_to_nm,
    nm::ip::{iface_ipv4_to_nm, iface_ipv6_to_nm},
    nm::ovs::{
        create_nm_ovs_br_set, create_nm_ovs_iface_set, create_ovs_port_nm_conn,
    },
    nm::profile::get_exist_profile,
    ErrorKind, Interface, InterfaceIpv4, InterfaceIpv6, InterfaceType,
    NetworkState, NmstateError,
};

pub(crate) const NM_SETTING_BRIDGE_SETTING_NAME: &str = "bridge";
pub(crate) const NM_SETTING_WIRED_SETTING_NAME: &str = "802-3-ethernet";
pub(crate) const NM_SETTING_OVS_BRIDGE_SETTING_NAME: &str = "ovs-bridge";
pub(crate) const NM_SETTING_OVS_PORT_SETTING_NAME: &str = "ovs-port";
pub(crate) const NM_SETTING_OVS_IFACE_SETTING_NAME: &str = "ovs-interface";
pub(crate) const NM_SETTING_VETH_SETTING_NAME: &str = "veth";

pub(crate) fn nm_gen_conf(
    net_state: &NetworkState,
) -> Result<Vec<String>, NmstateError> {
    let mut ret = Vec::new();
    let ifaces = net_state.interfaces.to_vec();
    for iface in &ifaces {
        for nm_conn in iface_to_nm_connections(iface, &[], &[])? {
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
    }
    Ok(ret)
}

pub(crate) fn iface_to_nm_connections(
    iface: &Interface,
    exist_nm_conns: &[NmConnection],
    nm_ac_uuids: &[&str],
) -> Result<Vec<NmConnection>, NmstateError> {
    let mut ret: Vec<NmConnection> = Vec::new();
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
    let nm_ctrl_type = if let Some(ctrl_type) = &base_iface.controller_type {
        Some(iface_type_to_nm(ctrl_type)?)
    } else {
        None
    };
    let nm_ctrl_type = nm_ctrl_type.as_deref();
    let ctrl_name = base_iface.controller.as_deref();
    let mut nm_conn = gen_nm_connection(
        &base_iface.name,
        &uuid,
        &iface_type_to_nm(&base_iface.iface_type)?,
        ctrl_name,
        nm_ctrl_type,
        iface.is_controller(),
    );

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
    let mut nm_wired_set = NmSettingWired::new();
    let mut flag_need_wired = false;
    if let Some(mac) = &base_iface.mac_address {
        flag_need_wired = true;
        nm_wired_set.cloned_mac_address = Some(mac.to_string());
    }
    if flag_need_wired {
        nm_conn.wired = Some(nm_wired_set);
    }

    if let Interface::OvsBridge(ovs_br_iface) = iface {
        nm_conn.ovs_bridge = Some(create_nm_ovs_br_set(ovs_br_iface));
    }
    if let Interface::LinuxBridge(br_iface) = iface {
        if let Some(br_conf) = &br_iface.bridge {
            nm_conn.bridge = Some(linux_bridge_conf_to_nm(br_conf)?);
        }
    }
    if let Interface::OvsInterface(ovs_iface) = iface {
        nm_conn.ovs_iface = Some(create_nm_ovs_iface_set(ovs_iface));
    }
    ret.push(nm_conn);
    if let Interface::OvsBridge(ovs_br_iface) = iface {
        // For OVS Bridge, we should create its OVS port also
        for ovs_port_conf in ovs_br_iface.port_confs() {
            ret.push(create_ovs_port_nm_conn(
                &ovs_br_iface.base.name,
                ovs_port_conf,
            ))
        }
    }

    Ok(ret)
}

pub(crate) fn iface_type_to_nm(
    iface_type: &InterfaceType,
) -> Result<String, NmstateError> {
    match iface_type {
        InterfaceType::LinuxBridge => Ok("bridge".into()),
        InterfaceType::Ethernet => Ok("802-3-ethernet".into()),
        InterfaceType::OvsBridge => Ok("ovs-bridge".into()),
        InterfaceType::OvsInterface => Ok("ovs-interface".into()),
        InterfaceType::Other(s) => Ok(s.to_string()),
        _ => Err(NmstateError::new(
            ErrorKind::NotImplementedError,
            format!("Does not support iface type: {:?} yet", iface_type),
        )),
    }
}

pub(crate) fn create_index_for_nm_conns_by_name_type(
    nm_conns: &[NmConnection],
) -> HashMap<(&str, &str), Vec<&NmConnection>> {
    let mut ret: HashMap<(&str, &str), Vec<&NmConnection>> = HashMap::new();
    for nm_conn in nm_conns {
        if let Some(iface_name) = nm_conn.iface_name() {
            if let Some(mut nm_iface_type) = nm_conn.iface_type() {
                if nm_iface_type == NM_SETTING_VETH_SETTING_NAME {
                    nm_iface_type = NM_SETTING_WIRED_SETTING_NAME;
                }
                match ret.entry((iface_name, nm_iface_type)) {
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

pub(crate) fn create_index_for_nm_conns_by_ctrler_type(
    nm_conns: &[NmConnection],
) -> HashMap<(&str, &str), Vec<&NmConnection>> {
    let mut ret: HashMap<(&str, &str), Vec<&NmConnection>> = HashMap::new();
    for nm_conn in nm_conns {
        let ctrl_name = if let Some(c) = nm_conn.controller() {
            c
        } else {
            continue;
        };
        let nm_ctrl_type = if let Some(c) = nm_conn.controller_type() {
            c
        } else {
            continue;
        };
        match ret.entry((ctrl_name, nm_ctrl_type)) {
            Entry::Occupied(o) => {
                o.into_mut().push(nm_conn);
            }
            Entry::Vacant(v) => {
                v.insert(vec![nm_conn]);
            }
        };
    }
    ret
}

pub(crate) fn get_port_nm_conns<'a>(
    nm_conn: &'a NmConnection,
    nm_conns_ctrler_type_index: &HashMap<
        (&'a str, &'a str),
        Vec<&'a NmConnection>,
    >,
) -> Vec<&'a NmConnection> {
    let mut ret: Vec<&NmConnection> = Vec::new();
    if let Some(nm_iface_type) = nm_conn.iface_type() {
        if let Some(uuid) = nm_conn.uuid() {
            if let Some(port_nm_conns) =
                nm_conns_ctrler_type_index.get(&(uuid, nm_iface_type))
            {
                for port_nm_conn in port_nm_conns {
                    ret.push(port_nm_conn);
                    if port_nm_conn.iface_type() == Some("ovs-port") {
                        for ovs_iface_nm_conn in get_port_nm_conns(
                            port_nm_conn,
                            nm_conns_ctrler_type_index,
                        ) {
                            ret.push(ovs_iface_nm_conn)
                        }
                    }
                }
            }
        }

        if let Some(name) = nm_conn.iface_name() {
            if let Some(port_nm_conns) =
                nm_conns_ctrler_type_index.get(&(name, nm_iface_type))
            {
                for port_nm_conn in port_nm_conns {
                    ret.push(port_nm_conn);
                    if port_nm_conn.iface_type() == Some("ovs-port") {
                        for ovs_iface_nm_conn in get_port_nm_conns(
                            port_nm_conn,
                            nm_conns_ctrler_type_index,
                        ) {
                            ret.push(ovs_iface_nm_conn)
                        }
                    }
                }
            }
        }
    }
    ret
}

pub(crate) fn gen_nm_connection(
    iface_name: &str,
    uuid: &str,
    nm_iface_type: &str,
    ctrl_name: Option<&str>,
    nm_ctrl_type: Option<&str>,
    is_controller: bool,
) -> NmConnection {
    let mut nm_conn = NmConnection::new();

    // OVS port already has it own prefix
    let conn_name = if nm_iface_type == "ovs-bridge" {
        format!("ovs-br-{}", iface_name)
    } else if nm_iface_type == "ovs-interface" {
        format!("ovs-iface-{}", iface_name)
    } else {
        iface_name.to_string()
    };

    let mut nm_conn_set = NmSettingConnection::new();
    nm_conn_set.id = Some(conn_name);
    nm_conn_set.uuid = Some(uuid.to_string());
    nm_conn_set.iface_type = Some(nm_iface_type.to_string());
    nm_conn_set.iface_name = Some(iface_name.to_string());
    nm_conn_set.autoconnect = Some(true);
    nm_conn_set.autoconnect_ports =
        if is_controller { Some(true) } else { None };

    if let Some(ctrl_name) = ctrl_name {
        if let Some(nm_ctrl_type) = nm_ctrl_type {
            nm_conn_set.controller = Some(ctrl_name.to_string());
            nm_conn_set.controller_type = if nm_ctrl_type == "ovs-bridge"
                && nm_iface_type != "ovs-port"
            {
                Some("ovs-port".to_string())
            } else {
                Some(nm_ctrl_type.to_string())
            };
        }
    }
    nm_conn.connection = Some(nm_conn_set);

    nm_conn
}
