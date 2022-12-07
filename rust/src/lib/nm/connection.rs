use std::collections::{hash_map::Entry, HashMap};

use nm_dbus::{
    NmApi, NmConnection, NmSettingConnection, NmSettingMacVlan, NmSettingVeth,
    NmSettingVlan, NmSettingVrf, NmSettingVxlan,
};

use crate::{
    nm::bond::gen_nm_bond_setting,
    nm::bridge::{gen_nm_br_port_setting, gen_nm_br_setting},
    nm::ip::gen_nm_ip_setting,
    nm::ovs::{
        create_ovs_port_nm_conn, gen_nm_ovs_br_setting,
        gen_nm_ovs_ext_ids_setting, gen_nm_ovs_iface_setting,
    },
    nm::profile::get_exist_profile,
    nm::sriov::gen_nm_sriov_setting,
    nm::veth::create_veth_peer_profile_if_not_found,
    nm::wired::gen_nm_wired_setting,
    ErrorKind, Interface, InterfaceType, NetworkState, NmstateError,
};

pub(crate) const NM_SETTING_BRIDGE_SETTING_NAME: &str = "bridge";
pub(crate) const NM_SETTING_WIRED_SETTING_NAME: &str = "802-3-ethernet";
pub(crate) const NM_SETTING_OVS_BRIDGE_SETTING_NAME: &str = "ovs-bridge";
pub(crate) const NM_SETTING_OVS_PORT_SETTING_NAME: &str = "ovs-port";
pub(crate) const NM_SETTING_OVS_IFACE_SETTING_NAME: &str = "ovs-interface";
pub(crate) const NM_SETTING_VETH_SETTING_NAME: &str = "veth";
pub(crate) const NM_SETTING_BOND_SETTING_NAME: &str = "bond";
pub(crate) const NM_SETTING_DUMMY_SETTING_NAME: &str = "dummy";
pub(crate) const NM_SETTING_MACVLAN_SETTING_NAME: &str = "macvlan";
pub(crate) const NM_SETTING_VRF_SETTING_NAME: &str = "vrf";
pub(crate) const NM_SETTING_VLAN_SETTING_NAME: &str = "vlan";
pub(crate) const NM_SETTING_VXLAN_SETTING_NAME: &str = "vxlan";

pub(crate) fn nm_gen_conf(
    net_state: &NetworkState,
) -> Result<Vec<String>, NmstateError> {
    let mut ret = Vec::new();
    let ifaces = net_state.interfaces.to_vec();
    for iface in &ifaces {
        let mut ctrl_iface: Option<&Interface> = None;
        if let Some(ctrl_iface_name) = &iface.base_iface().controller {
            if let Some(ctrl_type) = &iface.base_iface().controller_type {
                ctrl_iface = net_state
                    .interfaces
                    .get_iface(ctrl_iface_name, ctrl_type.clone());
            }
        }

        for nm_conn in
            iface_to_nm_connections(iface, ctrl_iface, &[], &[], false)?
        {
            ret.push(match nm_conn.to_keyfile() {
                Ok(s) => s,
                Err(e) => {
                    return Err(NmstateError::new(
                        ErrorKind::PluginFailure,
                        format!(
                        "Bug in NM plugin, failed to generate configure: {e}"
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
    ctrl_iface: Option<&Interface>,
    exist_nm_conns: &[NmConnection],
    nm_ac_uuids: &[&str],
    veth_peer_exist_in_desire: bool,
) -> Result<Vec<NmConnection>, NmstateError> {
    let mut ret: Vec<NmConnection> = Vec::new();
    let base_iface = iface.base_iface();
    let exist_nm_conn = get_exist_profile(
        exist_nm_conns,
        &base_iface.name,
        &base_iface.iface_type,
        nm_ac_uuids,
    );

    let mut nm_conn = exist_nm_conn.cloned().unwrap_or_default();

    gen_nm_conn_setting(iface, &mut nm_conn)?;
    gen_nm_ip_setting(
        iface,
        iface.base_iface().routes.as_deref(),
        iface.base_iface().rules.as_deref(),
        &mut nm_conn,
    )?;
    gen_nm_wired_setting(iface, &mut nm_conn);
    gen_nm_ovs_ext_ids_setting(iface, &mut nm_conn);

    match iface {
        Interface::OvsBridge(ovs_br_iface) => {
            gen_nm_ovs_br_setting(ovs_br_iface, &mut nm_conn);
            // For OVS Bridge, we should create its OVS port also
            for ovs_port_conf in ovs_br_iface.port_confs() {
                let exist_nm_ovs_port_conn = get_exist_profile(
                    exist_nm_conns,
                    &ovs_port_conf.name,
                    &InterfaceType::Other("ovs-port".to_string()),
                    nm_ac_uuids,
                );
                ret.push(create_ovs_port_nm_conn(
                    &ovs_br_iface.base.name,
                    ovs_port_conf,
                    exist_nm_ovs_port_conn,
                )?)
            }
        }
        Interface::LinuxBridge(br_iface) => {
            gen_nm_br_setting(br_iface, &mut nm_conn);
        }
        Interface::Bond(bond_iface) => {
            gen_nm_bond_setting(bond_iface, &mut nm_conn);
        }
        Interface::OvsInterface(_) => {
            // TODO Support OVS Patch interface
            gen_nm_ovs_iface_setting(&mut nm_conn);
        }
        Interface::Vlan(vlan_iface) => {
            if let Some(conf) = vlan_iface.vlan.as_ref() {
                nm_conn.vlan = Some(NmSettingVlan::from(conf))
            }
        }
        Interface::Vxlan(vxlan_iface) => {
            if let Some(conf) = vxlan_iface.vxlan.as_ref() {
                nm_conn.vxlan = Some(NmSettingVxlan::from(conf))
            }
        }
        Interface::Ethernet(eth_iface) => {
            if let Some(veth_conf) = eth_iface.veth.as_ref() {
                nm_conn.veth = Some(NmSettingVeth::from(veth_conf));
                if !veth_peer_exist_in_desire {
                    // Create NM connect for veth peer so that
                    // veth could be in up state
                    ret.push(create_veth_peer_profile_if_not_found(
                        veth_conf.peer.as_str(),
                        exist_nm_conns,
                    )?);
                }
            }
            gen_nm_sriov_setting(eth_iface, &mut nm_conn);
        }
        Interface::MacVlan(iface) => {
            if let Some(conf) = iface.mac_vlan.as_ref() {
                nm_conn.mac_vlan = Some(NmSettingMacVlan::from(conf));
            }
        }
        Interface::MacVtap(iface) => {
            if let Some(conf) = iface.mac_vtap.as_ref() {
                nm_conn.mac_vlan = Some(NmSettingMacVlan::from(conf));
            }
        }
        Interface::Vrf(iface) => {
            if let Some(vrf_conf) = iface.vrf.as_ref() {
                nm_conn.vrf = Some(NmSettingVrf::from(vrf_conf));
            }
        }
        _ => (),
    };

    if let Some(Interface::LinuxBridge(br_iface)) = ctrl_iface {
        gen_nm_br_port_setting(br_iface, &mut nm_conn);
    }

    // When detaching a OVS system interface from OVS bridge, we should remove
    // its NmSettingOvsIface setting
    if base_iface.controller.is_none() {
        nm_conn.ovs_iface = None;
    }

    ret.insert(0, nm_conn);

    Ok(ret)
}

pub(crate) fn iface_type_to_nm(
    iface_type: &InterfaceType,
) -> Result<String, NmstateError> {
    match iface_type {
        InterfaceType::LinuxBridge => Ok("bridge".into()),
        InterfaceType::Bond => Ok("bond".into()),
        InterfaceType::Ethernet => Ok("802-3-ethernet".into()),
        InterfaceType::OvsBridge => Ok("ovs-bridge".into()),
        InterfaceType::OvsInterface => Ok("ovs-interface".into()),
        InterfaceType::Vlan => Ok("vlan".to_string()),
        InterfaceType::Vxlan => Ok("vxlan".to_string()),
        InterfaceType::Dummy => Ok("dummy".to_string()),
        InterfaceType::MacVlan => Ok("macvlan".to_string()),
        InterfaceType::MacVtap => Ok("macvlan".to_string()),
        InterfaceType::Vrf => Ok("vrf".to_string()),
        InterfaceType::Veth => Ok("veth".to_string()),
        InterfaceType::Other(s) => Ok(s.to_string()),
        _ => Err(NmstateError::new(
            ErrorKind::NotImplementedError,
            format!("Does not support iface type: {iface_type:?} yet"),
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

pub(crate) fn gen_nm_conn_setting(
    iface: &Interface,
    nm_conn: &mut NmConnection,
) -> Result<(), NmstateError> {
    let mut nm_conn_set = if let Some(cur_nm_conn_set) = &nm_conn.connection {
        cur_nm_conn_set.clone()
    } else {
        let mut new_nm_conn_set = NmSettingConnection::new();
        let conn_name = match iface.iface_type() {
            InterfaceType::OvsBridge => {
                format!("ovs-br-{}", iface.name())
            }
            InterfaceType::Other(ref other_type)
                if other_type == "ovs-port" =>
            {
                format!("ovs-port-{}", iface.name())
            }
            InterfaceType::OvsInterface => {
                format!("ovs-iface-{}", iface.name())
            }
            _ => iface.name().to_string(),
        };

        new_nm_conn_set.id = Some(conn_name);
        new_nm_conn_set.uuid = Some(NmApi::uuid_gen());
        if new_nm_conn_set.iface_type.is_none() {
            // The `get_exist_profile()` already confirmed the existing
            // profile has correct `iface_type`. We should not override it.
            // The use case is, existing connection is veth, but user desire
            // ethernet interface, we should use existing interface type.
            new_nm_conn_set.iface_type =
                Some(iface_type_to_nm(&iface.iface_type())?);
        }
        new_nm_conn_set
    };

    nm_conn_set.iface_name = Some(iface.name().to_string());
    nm_conn_set.autoconnect = Some(true);
    nm_conn_set.autoconnect_ports = if iface.is_controller() {
        Some(true)
    } else {
        None
    };

    nm_conn_set.controller = None;
    nm_conn_set.controller_type = None;
    let nm_ctrl_type = iface
        .base_iface()
        .controller_type
        .as_ref()
        .map(iface_type_to_nm)
        .transpose()?;
    let nm_ctrl_type = nm_ctrl_type.as_deref();
    let ctrl_name = iface.base_iface().controller.as_deref();
    if let Some(ctrl_name) = ctrl_name {
        if let Some(nm_ctrl_type) = nm_ctrl_type {
            nm_conn_set.controller = Some(ctrl_name.to_string());
            nm_conn_set.controller_type = if nm_ctrl_type == "ovs-bridge"
                && iface.iface_type()
                    != InterfaceType::Other("ovs-port".to_string())
            {
                Some("ovs-port".to_string())
            } else {
                Some(nm_ctrl_type.to_string())
            };
        }
    }
    nm_conn.connection = Some(nm_conn_set);
    Ok(())
}
