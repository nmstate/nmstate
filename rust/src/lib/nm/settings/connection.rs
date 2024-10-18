// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{
    NmConnection, NmIfaceType, NmSettingConnection, NmSettingMacVlan,
    NmSettingVeth, NmSettingVrf, NmSettingVxlan, NmSettingsConnectionFlag,
};
use super::{
    bond::{gen_nm_bond_port_setting, gen_nm_bond_setting},
    bridge::{gen_nm_br_port_setting, gen_nm_br_setting},
    ethtool::gen_ethtool_setting,
    hsr::gen_nm_hsr_setting,
    ieee8021x::gen_nm_802_1x_setting,
    infiniband::gen_nm_ib_setting,
    ip::gen_nm_ip_setting,
    ipvlan::gen_nm_ipvlan_setting,
    loopback::gen_nm_loopback_setting,
    macsec::gen_nm_macsec_setting,
    mptcp::apply_mptcp_conf,
    ovs::{
        create_ovs_port_nm_conn, fix_ovs_iface_controller_setting,
        gen_nm_iface_ovs_db_setting, gen_nm_ovs_br_setting,
        gen_nm_ovs_iface_setting, get_ovs_port_name,
    },
    sriov::gen_nm_sriov_setting,
    user::gen_nm_user_setting,
    veth::create_veth_peer_profile_if_not_found,
    vlan::gen_nm_vlan_setting,
    vpn::gen_nm_ipsec_vpn_setting,
    wired::gen_nm_wired_setting,
};

use crate::{
    ErrorKind, Interface, InterfaceIdentifier, InterfaceType, MergedInterface,
    MergedNetworkState, NmstateError, OvsBridgePortConfig,
};

pub(crate) fn iface_to_nm_connections(
    merged_iface: &MergedInterface,
    merged_state: &MergedNetworkState,
    exist_nm_conns: &[NmConnection],
    nm_ac_uuids: &[&str],
    gen_conf_mode: bool,
) -> Result<Vec<NmConnection>, NmstateError> {
    let mut ret: Vec<NmConnection> = Vec::new();

    let mut iface = if let Some(i) = merged_iface.for_apply.as_ref() {
        i.clone()
    } else {
        return Ok(ret);
    };

    let exist_nm_conn = if iface.base_iface().identifier
        == Some(InterfaceIdentifier::MacAddress)
    {
        get_exist_profile_by_profile_name(
            exist_nm_conns,
            iface
                .base_iface()
                .profile_name
                .as_deref()
                .unwrap_or(iface.base_iface().name.as_str()),
            &iface.base_iface().iface_type,
        )
    } else {
        get_exist_profile(
            exist_nm_conns,
            &iface.base_iface().name,
            &iface.base_iface().iface_type,
            nm_ac_uuids,
        )
    };

    if iface.is_up_exist_config() {
        if let Some(nm_conn) = exist_nm_conn {
            if !iface.is_userspace()
                && nm_conn.flags.contains(&NmSettingsConnectionFlag::External)
            {
                // User want to convert current state to persistent
                // But NetworkManager does not include routes for external
                // managed interfaces.
                if let Some(cur_iface) = merged_iface.current.as_ref() {
                    return persisten_iface_cur_conf(
                        cur_iface,
                        merged_state,
                        exist_nm_conns,
                        nm_ac_uuids,
                        gen_conf_mode,
                    );
                }
            }
            return Ok(vec![nm_conn.clone()]);
        } else if !iface.is_userspace() {
            // User want to convert unmanaged interface to managed
            if let Some(cur_iface) = merged_iface.current.as_ref() {
                if cur_iface.is_ignore() {
                    return persisten_iface_cur_conf(
                        cur_iface,
                        merged_state,
                        exist_nm_conns,
                        nm_ac_uuids,
                        gen_conf_mode,
                    );
                }
            }
        }
    }

    // If exist_nm_conn is None and desired state did not mention IP settings,
    // we are supported to preserve current IP state instead of setting ipv4 and
    // ipv6 disabled.
    if exist_nm_conn.is_none() {
        preserve_current_ip(&mut iface, merged_iface.current.as_ref());
    }

    let iface = &iface;

    let mut nm_conn = exist_nm_conn.cloned().unwrap_or_default();
    nm_conn.flags = Vec::new();

    // Use stable UUID if in gen_conf mode.
    // This enable us to generate the same output for `nm_gen_conf()`
    // when the desire state is the same.
    let stable_uuid = gen_conf_mode;

    gen_nm_conn_setting(iface, &mut nm_conn, stable_uuid)?;
    gen_nm_ip_setting(
        iface,
        iface.base_iface().routes.as_deref(),
        &mut nm_conn,
    )?;
    // InfiniBand over IP and loopback can not have layer 2 configuration.
    if iface.iface_type() != InterfaceType::InfiniBand
        && iface.iface_type() != InterfaceType::Loopback
    {
        gen_nm_wired_setting(iface, &mut nm_conn);
    }
    gen_nm_iface_ovs_db_setting(iface, &mut nm_conn);
    gen_nm_802_1x_setting(iface, &mut nm_conn);
    gen_nm_user_setting(iface, &mut nm_conn);
    gen_ethtool_setting(iface, &mut nm_conn)?;

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
                    stable_uuid,
                )?)
            }
        }
        Interface::LinuxBridge(_) => {
            gen_nm_br_setting(merged_iface, &mut nm_conn);
        }
        Interface::Bond(bond_iface) => {
            gen_nm_bond_setting(bond_iface, &mut nm_conn);
        }
        Interface::OvsInterface(iface) => {
            gen_nm_ovs_iface_setting(iface, &mut nm_conn);
        }
        Interface::Vlan(vlan_iface) => {
            gen_nm_vlan_setting(vlan_iface, &mut nm_conn);
        }
        Interface::Vxlan(vxlan_iface) => {
            if let Some(conf) = vxlan_iface.vxlan.as_ref() {
                nm_conn.vxlan = Some(NmSettingVxlan::from(conf))
            }
        }
        Interface::Ethernet(eth_iface) => {
            if let Some(veth_conf) = eth_iface.veth.as_ref() {
                nm_conn.veth = Some(NmSettingVeth::from(veth_conf));
                if merged_state
                    .interfaces
                    .kernel_ifaces
                    .get(veth_conf.peer.as_str())
                    .and_then(|i| i.for_apply.as_ref())
                    .is_none()
                    && !merged_state.interfaces.ignored_ifaces.contains(&(
                        veth_conf.peer.to_string(),
                        InterfaceType::Ethernet,
                    ))
                {
                    // Create NM connect for veth peer so that
                    // veth could be in up state
                    log::info!(
                        "Creating veth peer profile {} for {}",
                        veth_conf.peer.as_str(),
                        eth_iface.base.name.as_str()
                    );
                    ret.push(create_veth_peer_profile_if_not_found(
                        veth_conf.peer.as_str(),
                        eth_iface.base.name.as_str(),
                        exist_nm_conns,
                        stable_uuid,
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
        Interface::InfiniBand(iface) => {
            gen_nm_ib_setting(iface, &mut nm_conn);
        }
        Interface::MacSec(iface) => {
            gen_nm_macsec_setting(iface, &mut nm_conn);
        }
        Interface::Loopback(iface) => {
            gen_nm_loopback_setting(iface, &mut nm_conn);
        }
        Interface::Hsr(iface) => {
            gen_nm_hsr_setting(iface, &mut nm_conn);
        }
        Interface::Ipsec(iface) => {
            gen_nm_ipsec_vpn_setting(iface, &mut nm_conn);
        }
        Interface::IpVlan(iface) => {
            gen_nm_ipvlan_setting(iface, &mut nm_conn);
        }
        _ => (),
    };

    if nm_conn.controller_type() != Some(&NmIfaceType::Bond) {
        nm_conn.bond_port = None;
    }

    if nm_conn.controller_type() != Some(&NmIfaceType::Bridge) {
        nm_conn.bridge_port = None;
    }

    if nm_conn.controller_type() != Some(&NmIfaceType::OvsPort) {
        nm_conn.ovs_iface = None;
    }

    if let (Some(ctrl), Some(ctrl_type)) = (
        iface.base_iface().controller.as_ref(),
        iface.base_iface().controller_type.as_ref(),
    ) {
        if let Some(ctrl_iface) =
            merged_state.interfaces.get_iface(ctrl, ctrl_type.clone())
        {
            match &ctrl_iface.merged {
                Interface::Bond(bond_iface) => {
                    gen_nm_bond_port_setting(bond_iface, &mut nm_conn);
                }
                Interface::LinuxBridge(br_iface) => {
                    gen_nm_br_port_setting(br_iface, &mut nm_conn);
                }
                Interface::OvsBridge(ovs_br_iface) => {
                    fix_ovs_iface_controller_setting(
                        iface,
                        &mut nm_conn,
                        &merged_state.interfaces,
                    );
                    let ovs_port_name =
                        match get_ovs_port_name(ovs_br_iface, iface.name()) {
                            Some(name) => name,
                            None => {
                                // We are attaching iface to OVS bridge using
                                // `controller` property
                                iface.name().to_string()
                            }
                        };
                    // When user attaching change controller property
                    // on OVS system or internal interface, we should
                    // modify it OVS port also.
                    if !ctrl_iface.is_changed()
                        && merged_iface
                            .for_apply
                            .as_ref()
                            .and_then(|i| i.base_iface().controller.as_ref())
                            != merged_iface.current.as_ref().and_then(|i| {
                                i.base_iface().controller.as_ref()
                            })
                    {
                        let exist_nm_ovs_port_conn = get_exist_profile(
                            exist_nm_conns,
                            &ovs_port_name,
                            &InterfaceType::Other("ovs-port".to_string()),
                            nm_ac_uuids,
                        );
                        ret.push(create_ovs_port_nm_conn(
                            ctrl,
                            &OvsBridgePortConfig {
                                name: ovs_port_name,
                                ..Default::default()
                            },
                            exist_nm_ovs_port_conn,
                            stable_uuid,
                        )?);
                    }
                }
                _ => (),
            }
        }
    }

    // When detaching a OVS system interface from OVS bridge, we should remove
    // its NmSettingOvsIface setting
    if iface.base_iface().controller.as_deref() == Some("") {
        nm_conn.ovs_iface = None;
    }

    ret.insert(0, nm_conn);

    Ok(ret)
}

pub(crate) fn iface_type_to_nm(
    iface_type: &InterfaceType,
) -> Result<NmIfaceType, NmstateError> {
    match iface_type {
        InterfaceType::LinuxBridge => Ok(NmIfaceType::Bridge),
        InterfaceType::Bond => Ok(NmIfaceType::Bond),
        InterfaceType::Ethernet => Ok(NmIfaceType::Ethernet),
        InterfaceType::OvsBridge => Ok(NmIfaceType::OvsBridge),
        InterfaceType::OvsInterface => Ok(NmIfaceType::OvsIface),
        InterfaceType::Vlan => Ok(NmIfaceType::Vlan),
        InterfaceType::Vxlan => Ok(NmIfaceType::Vxlan),
        InterfaceType::Dummy => Ok(NmIfaceType::Dummy),
        InterfaceType::MacVlan => Ok(NmIfaceType::Macvlan),
        InterfaceType::MacVtap => Ok(NmIfaceType::Macvlan),
        InterfaceType::Vrf => Ok(NmIfaceType::Vrf),
        InterfaceType::Veth => Ok(NmIfaceType::Veth),
        InterfaceType::InfiniBand => Ok(NmIfaceType::Infiniband),
        InterfaceType::Loopback => Ok(NmIfaceType::Loopback),
        InterfaceType::MacSec => Ok(NmIfaceType::Macsec),
        InterfaceType::Hsr => Ok(NmIfaceType::Hsr),
        InterfaceType::Ipsec => Ok(NmIfaceType::Vpn),
        InterfaceType::IpVlan => Ok(NmIfaceType::Ipvlan),
        InterfaceType::Other(s) => Ok(NmIfaceType::from(s.as_str())),
        _ => Err(NmstateError::new(
            ErrorKind::NotImplementedError,
            format!("Does not support iface type: {iface_type:?} yet"),
        )),
    }
}

pub(crate) fn gen_nm_conn_setting(
    iface: &Interface,
    nm_conn: &mut NmConnection,
    stable_uuid: bool,
) -> Result<(), NmstateError> {
    let mut nm_conn_set = if let Some(cur_nm_conn_set) = &nm_conn.connection {
        let mut new_nm_conn_set = cur_nm_conn_set.clone();
        // Change existing connection's profile_name if desired explicitly
        if let Some(n) = iface.base_iface().profile_name.as_deref() {
            new_nm_conn_set.id = Some(n.to_string());
        }
        new_nm_conn_set
    } else {
        let mut new_nm_conn_set = NmSettingConnection::default();
        let conn_name =
            if let Some(n) = iface.base_iface().profile_name.as_deref() {
                n.to_string()
            } else {
                match iface.iface_type() {
                    InterfaceType::OvsBridge => {
                        format!("{}-br", iface.name())
                    }
                    InterfaceType::Other(ref other_type)
                        if other_type == "ovs-port" =>
                    {
                        format!("{}-port", iface.name())
                    }
                    InterfaceType::OvsInterface => {
                        format!("{}-if", iface.name())
                    }
                    _ => iface.name().to_string(),
                }
            };

        new_nm_conn_set.id = Some(conn_name);
        new_nm_conn_set.uuid = Some(if stable_uuid {
            uuid_from_name_and_type(iface.name(), &iface.iface_type())
        } else {
            // Use Linux random number generator (RNG) to generate UUID
            uuid::Uuid::new_v4().hyphenated().to_string()
        });
        new_nm_conn_set.iface_type =
            Some(iface_type_to_nm(&iface.iface_type())?);
        if let Interface::Ethernet(eth_iface) = iface {
            if eth_iface.veth.is_some() {
                new_nm_conn_set.iface_type = Some(NmIfaceType::Veth);
            }
        }
        new_nm_conn_set
    };

    if iface.iface_type() != InterfaceType::Ipsec
        && iface.base_iface().identifier.unwrap_or_default()
            == InterfaceIdentifier::Name
    {
        nm_conn_set.iface_name = Some(iface.name().to_string());
    } else {
        nm_conn_set.iface_name = None;
    }
    nm_conn_set.autoconnect = Some(true);
    nm_conn_set.autoconnect_ports = if iface.is_controller()
        || iface.iface_type() == InterfaceType::Other("ovs-port".to_string())
    {
        Some(true)
    } else {
        None
    };

    let nm_ctrl_type = iface
        .base_iface()
        .controller_type
        .as_ref()
        .map(iface_type_to_nm)
        .transpose()?;
    let ctrl_name = iface.base_iface().controller.as_deref();
    if let Some(ctrl_name) = ctrl_name {
        if ctrl_name.is_empty() {
            nm_conn_set.controller = None;
            nm_conn_set.controller_type = None;
        } else if let Some(nm_ctrl_type) = nm_ctrl_type {
            nm_conn_set.controller = Some(ctrl_name.to_string());
            nm_conn_set.controller_type = if nm_ctrl_type
                == NmIfaceType::OvsBridge
                && iface.iface_type()
                    != InterfaceType::Other("ovs-port".to_string())
            {
                Some(NmIfaceType::OvsPort)
            } else {
                Some(nm_ctrl_type)
            };
        }
    }
    if let Some(lldp_conf) = iface.base_iface().lldp.as_ref() {
        nm_conn_set.lldp = Some(lldp_conf.enabled);
    }
    if let Some(mptcp_conf) = iface.base_iface().mptcp.as_ref() {
        apply_mptcp_conf(&mut nm_conn_set, mptcp_conf)?;
    }

    nm_conn.connection = Some(nm_conn_set);

    Ok(())
}

fn uuid_from_name_and_type(
    iface_name: &str,
    iface_type: &InterfaceType,
) -> String {
    uuid::Uuid::new_v5(
        &uuid::Uuid::NAMESPACE_URL,
        format!("{iface_type}://{iface_name}").as_bytes(),
    )
    .hyphenated()
    .to_string()
}

// Found existing profile, prefer the activated one
pub(crate) fn get_exist_profile<'a>(
    exist_nm_conns: &'a [NmConnection],
    iface_name: &str,
    iface_type: &InterfaceType,
    nm_ac_uuids: &[&str],
) -> Option<&'a NmConnection> {
    let mut found_nm_conns: Vec<&NmConnection> = Vec::new();
    let nm_iface_type = if let Ok(t) = iface_type_to_nm(iface_type) {
        t
    } else {
        return None;
    };
    for exist_nm_conn in exist_nm_conns {
        if nm_iface_type == NmIfaceType::Vpn {
            if exist_nm_conn.id() == Some(iface_name) {
                if let Some(uuid) = exist_nm_conn.uuid() {
                    // Prefer activated connection
                    if nm_ac_uuids.contains(&uuid) {
                        return Some(exist_nm_conn);
                    }
                }
                found_nm_conns.push(exist_nm_conn);
            }
        } else if exist_nm_conn.iface_name() == Some(iface_name)
            && (exist_nm_conn.iface_type() == Some(&nm_iface_type)
                || (nm_iface_type == NmIfaceType::Ethernet
                    && exist_nm_conn.iface_type() == Some(&NmIfaceType::Veth)))
        {
            if let Some(uuid) = exist_nm_conn.uuid() {
                // Prefer activated connection
                if nm_ac_uuids.contains(&uuid) {
                    return Some(exist_nm_conn);
                }
            }
            found_nm_conns.push(exist_nm_conn);
        }
    }
    found_nm_conns.pop()
}

fn get_exist_profile_by_profile_name<'a>(
    exist_nm_conns: &'a [NmConnection],
    profile_name: &str,
    iface_type: &InterfaceType,
) -> Option<&'a NmConnection> {
    for exist_nm_conn in exist_nm_conns {
        let nm_iface_type = if let Ok(t) = iface_type_to_nm(iface_type) {
            t
        } else {
            continue;
        };
        if exist_nm_conn.id() == Some(profile_name)
            && exist_nm_conn.iface_type() == Some(&nm_iface_type)
        {
            return Some(exist_nm_conn);
        }
    }
    None
}

fn persisten_iface_cur_conf(
    cur_iface: &Interface,
    merged_state: &MergedNetworkState,
    exist_nm_conns: &[NmConnection],
    nm_ac_uuids: &[&str],
    gen_conf_mode: bool,
) -> Result<Vec<NmConnection>, NmstateError> {
    let mut iface = cur_iface.clone();
    iface.base_iface_mut().routes =
        merged_state.routes.merged.get(iface.name()).cloned();
    if let Interface::Ethernet(eth_iface) = &mut iface {
        eth_iface.veth = None;
        eth_iface.base.iface_type = InterfaceType::Ethernet;
    }
    let merged_iface = MergedInterface::new(Some(iface), None)?;

    iface_to_nm_connections(
        &merged_iface,
        merged_state,
        exist_nm_conns,
        nm_ac_uuids,
        gen_conf_mode,
    )
}

fn preserve_current_ip(iface: &mut Interface, cur_iface: Option<&Interface>) {
    if iface.base_iface().ipv4.is_none() {
        iface.base_iface_mut().ipv4 =
            cur_iface.as_ref().and_then(|i| i.base_iface().ipv4.clone());
    }
    if iface.base_iface().ipv6.is_none() {
        iface.base_iface_mut().ipv6 =
            cur_iface.as_ref().and_then(|i| i.base_iface().ipv6.clone());
    }
}
