// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{
    NmConnection, NmSettingConnection, NmSettingMacVlan, NmSettingVeth,
    NmSettingVrf, NmSettingVxlan, NmSettingsConnectionFlag,
};
use super::{
    bond::{gen_nm_bond_port_setting, gen_nm_bond_setting},
    bridge::{gen_nm_br_port_setting, gen_nm_br_setting},
    ethtool::gen_ethtool_setting,
    hsr::gen_nm_hsr_setting,
    ieee8021x::gen_nm_802_1x_setting,
    infiniband::gen_nm_ib_setting,
    ip::gen_nm_ip_setting,
    loopback::gen_nm_loopback_setting,
    macsec::gen_nm_macsec_setting,
    mptcp::apply_mptcp_conf,
    ovs::{
        create_ovs_port_nm_conn, gen_nm_iface_ovs_db_setting,
        gen_nm_ovs_br_setting, gen_nm_ovs_iface_setting, get_ovs_port_name,
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

pub(crate) const NM_SETTING_BRIDGE_SETTING_NAME: &str = "bridge";
pub(crate) const NM_SETTING_WIRED_SETTING_NAME: &str = "802-3-ethernet";
pub(crate) const NM_SETTING_OVS_BRIDGE_SETTING_NAME: &str = "ovs-bridge";
pub(crate) const NM_SETTING_OVS_PORT_SETTING_NAME: &str = "ovs-port";
pub(crate) const NM_SETTING_OVS_IFACE_SETTING_NAME: &str = "ovs-interface";
pub(crate) const NM_SETTING_VETH_SETTING_NAME: &str = "veth";
pub(crate) const NM_SETTING_BOND_SETTING_NAME: &str = "bond";
pub(crate) const NM_SETTING_DUMMY_SETTING_NAME: &str = "dummy";
pub(crate) const NM_SETTING_MACSEC_SETTING_NAME: &str = "macsec";
pub(crate) const NM_SETTING_MACVLAN_SETTING_NAME: &str = "macvlan";
pub(crate) const NM_SETTING_VRF_SETTING_NAME: &str = "vrf";
pub(crate) const NM_SETTING_VLAN_SETTING_NAME: &str = "vlan";
pub(crate) const NM_SETTING_VXLAN_SETTING_NAME: &str = "vxlan";
pub(crate) const NM_SETTING_INFINIBAND_SETTING_NAME: &str = "infiniband";
pub(crate) const NM_SETTING_LOOPBACK_SETTING_NAME: &str = "loopback";
pub(crate) const NM_SETTING_HSR_SETTING_NAME: &str = "hsr";
pub(crate) const NM_SETTING_VPN_SETTING_NAME: &str = "vpn";

pub(crate) const NM_SETTING_USER_SPACES: [&str; 2] = [
    NM_SETTING_OVS_BRIDGE_SETTING_NAME,
    NM_SETTING_OVS_PORT_SETTING_NAME,
];

pub(crate) const SUPPORTED_NM_KERNEL_IFACE_TYPES: [&str; 14] = [
    NM_SETTING_WIRED_SETTING_NAME,
    NM_SETTING_VETH_SETTING_NAME,
    NM_SETTING_BOND_SETTING_NAME,
    NM_SETTING_DUMMY_SETTING_NAME,
    NM_SETTING_BRIDGE_SETTING_NAME,
    NM_SETTING_OVS_IFACE_SETTING_NAME,
    NM_SETTING_VRF_SETTING_NAME,
    NM_SETTING_VLAN_SETTING_NAME,
    NM_SETTING_VXLAN_SETTING_NAME,
    NM_SETTING_MACVLAN_SETTING_NAME,
    NM_SETTING_LOOPBACK_SETTING_NAME,
    NM_SETTING_INFINIBAND_SETTING_NAME,
    NM_SETTING_MACSEC_SETTING_NAME,
    NM_SETTING_HSR_SETTING_NAME,
];

pub(crate) fn iface_to_nm_connections(
    merged_iface: &MergedInterface,
    merged_state: &MergedNetworkState,
    exist_nm_conns: &[NmConnection],
    nm_ac_uuids: &[&str],
    gen_conf_mode: bool,
) -> Result<Vec<NmConnection>, NmstateError> {
    let mut ret: Vec<NmConnection> = Vec::new();

    let iface = if let Some(i) = merged_iface.for_apply.as_ref() {
        i
    } else {
        return Ok(ret);
    };

    let base_iface = iface.base_iface();
    let exist_nm_conn =
        if base_iface.identifier == Some(InterfaceIdentifier::MacAddress) {
            get_exist_profile_by_profile_name(
                exist_nm_conns,
                base_iface
                    .profile_name
                    .as_deref()
                    .unwrap_or(base_iface.name.as_str()),
                &base_iface.iface_type,
            )
        } else {
            get_exist_profile(
                exist_nm_conns,
                &base_iface.name,
                &base_iface.iface_type,
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

    // Use stable UUID if in gen_conf mode.
    // This enable us to generate the same output for `nm_gen_conf()`
    // when the desire state is the same.
    let stable_uuid = gen_conf_mode;

    let mut nm_conn = exist_nm_conn.cloned().unwrap_or_default();
    // The rollback of checkpoint of NetworkManager has bug if we reuse
    // the uuid of in-memory profile for on-disk profile:
    //   https://issues.redhat.com/browse/RHEL-31972
    if (!merged_state.memory_only)
        && (nm_conn.flags.contains(&NmSettingsConnectionFlag::Volatile)
            || nm_conn.flags.contains(&NmSettingsConnectionFlag::Unsaved))
    {
        // Indicate we are new NM connection now
        nm_conn.obj_path = String::new();
        if let Some(nm_conn_set) = nm_conn.connection.as_mut() {
            nm_conn_set.uuid =
                Some(gen_uuid(stable_uuid, iface.name(), &iface.iface_type()));
        }
    }
    nm_conn.flags = Vec::new();

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
        _ => (),
    };

    if nm_conn.controller_type() != Some(NM_SETTING_BOND_SETTING_NAME) {
        nm_conn.bond_port = None;
    }

    if nm_conn.controller_type() != Some(NM_SETTING_BRIDGE_SETTING_NAME) {
        nm_conn.bridge_port = None;
    }

    if nm_conn.controller_type() != Some(NM_SETTING_OVS_PORT_SETTING_NAME) {
        nm_conn.ovs_iface = None;
    }

    if let (Some(ctrl), Some(ctrl_type)) = (
        base_iface.controller.as_ref(),
        base_iface.controller_type.as_ref(),
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
                        let exist_nm_ovs_port_conn = if let Some(
                            ovs_port_name,
                        ) = get_ovs_port_name(
                            ovs_br_iface,
                            base_iface.name.as_str(),
                        ) {
                            get_exist_profile(
                                exist_nm_conns,
                                &ovs_port_name,
                                &InterfaceType::Other("ovs-port".to_string()),
                                nm_ac_uuids,
                            )
                        } else {
                            None
                        };
                        ret.push(create_ovs_port_nm_conn(
                            ctrl,
                            &OvsBridgePortConfig {
                                name: iface.name().to_string(),
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
    if base_iface.controller.as_deref() == Some("") {
        nm_conn.ovs_iface = None;
    }

    ret.insert(0, nm_conn);

    Ok(ret)
}

pub(crate) fn iface_type_to_nm(
    iface_type: &InterfaceType,
) -> Result<String, NmstateError> {
    match iface_type {
        InterfaceType::LinuxBridge => Ok(NM_SETTING_BRIDGE_SETTING_NAME.into()),
        InterfaceType::Bond => Ok(NM_SETTING_BOND_SETTING_NAME.into()),
        InterfaceType::Ethernet => Ok(NM_SETTING_WIRED_SETTING_NAME.into()),
        InterfaceType::OvsBridge => {
            Ok(NM_SETTING_OVS_BRIDGE_SETTING_NAME.into())
        }
        InterfaceType::OvsInterface => {
            Ok(NM_SETTING_OVS_IFACE_SETTING_NAME.into())
        }
        InterfaceType::Vlan => Ok(NM_SETTING_VLAN_SETTING_NAME.to_string()),
        InterfaceType::Vxlan => Ok(NM_SETTING_VXLAN_SETTING_NAME.to_string()),
        InterfaceType::Dummy => Ok(NM_SETTING_DUMMY_SETTING_NAME.to_string()),
        InterfaceType::MacVlan => {
            Ok(NM_SETTING_MACVLAN_SETTING_NAME.to_string())
        }
        InterfaceType::MacVtap => {
            Ok(NM_SETTING_MACVLAN_SETTING_NAME.to_string())
        }
        InterfaceType::Vrf => Ok(NM_SETTING_VRF_SETTING_NAME.to_string()),
        InterfaceType::Veth => Ok(NM_SETTING_VETH_SETTING_NAME.to_string()),
        InterfaceType::InfiniBand => {
            Ok(NM_SETTING_INFINIBAND_SETTING_NAME.to_string())
        }
        InterfaceType::Loopback => {
            Ok(NM_SETTING_LOOPBACK_SETTING_NAME.to_string())
        }
        InterfaceType::MacSec => Ok(NM_SETTING_MACSEC_SETTING_NAME.to_string()),
        InterfaceType::Hsr => Ok(NM_SETTING_HSR_SETTING_NAME.to_string()),
        InterfaceType::Ipsec => Ok(NM_SETTING_VPN_SETTING_NAME.to_string()),
        InterfaceType::Other(s) => Ok(s.to_string()),
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
        cur_nm_conn_set.clone()
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
        new_nm_conn_set.uuid =
            Some(gen_uuid(stable_uuid, iface.name(), &iface.iface_type()));
        new_nm_conn_set.iface_type =
            Some(iface_type_to_nm(&iface.iface_type())?);
        if let Interface::Ethernet(eth_iface) = iface {
            if eth_iface.veth.is_some() {
                new_nm_conn_set.iface_type =
                    Some(NM_SETTING_VETH_SETTING_NAME.to_string());
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
    nm_conn_set.autoconnect_ports = if iface.is_controller() {
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
    let nm_ctrl_type = nm_ctrl_type.as_deref();
    let ctrl_name = iface.base_iface().controller.as_deref();
    if let Some(ctrl_name) = ctrl_name {
        if ctrl_name.is_empty() {
            nm_conn_set.controller = None;
            nm_conn_set.controller_type = None;
        } else if let Some(nm_ctrl_type) = nm_ctrl_type {
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
    for exist_nm_conn in exist_nm_conns {
        let nm_iface_type = if let Ok(t) = iface_type_to_nm(iface_type) {
            t
        } else {
            continue;
        };
        if nm_iface_type == NM_SETTING_VPN_SETTING_NAME {
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
                || (nm_iface_type == NM_SETTING_WIRED_SETTING_NAME
                    && exist_nm_conn.iface_type()
                        == Some(NM_SETTING_VETH_SETTING_NAME)))
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
        merged_state.routes.indexed.get(iface.name()).cloned();
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

fn gen_uuid(
    stable_uuid: bool,
    iface_name: &str,
    iface_type: &InterfaceType,
) -> String {
    if stable_uuid {
        uuid_from_name_and_type(iface_name, iface_type)
    } else {
        // Use Linux random number generator (RNG) to generate UUID
        uuid::Uuid::new_v4().hyphenated().to_string()
    }
}
