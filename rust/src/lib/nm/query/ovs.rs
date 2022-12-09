// SPDX-License-Identifier: Apache-2.0

use std::convert::TryFrom;

use super::super::{
    nm_dbus::NmConnection,
    settings::{get_exist_profile, NM_SETTING_OVS_PORT_SETTING_NAME},
};

use crate::{
    BridgePortVlanConfig, BridgePortVlanMode, Interface, InterfaceType,
    Interfaces, NmstateError, OvsBridgeBondConfig, OvsBridgeBondMode,
    OvsBridgeBondPortConfig, OvsBridgeConfig, OvsBridgeOptions,
    OvsBridgePortConfig, OvsDpdkConfig, OvsPatchConfig,
};

pub(crate) fn nm_ovs_bridge_conf_get(
    nm_conn: &NmConnection,
    port_nm_conns: Option<&[&NmConnection]>,
) -> Result<OvsBridgeConfig, NmstateError> {
    let mut ovs_br_conf = OvsBridgeConfig::new();
    if let Some(nm_ovs_setting) = &nm_conn.ovs_bridge {
        let mut br_opts = OvsBridgeOptions::new();
        // The DBUS interface of NM does not return default values
        // We set default values to be consistent with old nmstate behavior
        br_opts.stp = match nm_ovs_setting.stp {
            Some(n) => Some(n),
            None => Some(false),
        };
        br_opts.rstp = match nm_ovs_setting.rstp {
            Some(n) => Some(n),
            None => Some(false),
        };
        br_opts.mcast_snooping_enable =
            match nm_ovs_setting.mcast_snooping_enable {
                Some(n) => Some(n),
                None => Some(false),
            };
        br_opts.fail_mode = match nm_ovs_setting.fail_mode.as_ref() {
            Some(m) => Some(m.to_string()),
            None => Some("".to_string()),
        };
        br_opts.datapath = match nm_ovs_setting.datapath_type.as_ref() {
            Some(m) => Some(m.to_string()),
            None => Some("".to_string()),
        };
        ovs_br_conf.options = Some(br_opts);
        if let Some(port_nm_conns) = port_nm_conns {
            ovs_br_conf.ports =
                Some(nm_ovs_bridge_conf_port_get(port_nm_conns));
        }
    }
    Ok(ovs_br_conf)
}

fn nm_ovs_bridge_conf_port_get(
    nm_conns: &[&NmConnection],
) -> Vec<OvsBridgePortConfig> {
    let mut ret = Vec::new();
    for nm_conn in nm_conns {
        if nm_conn.iface_type() == Some("ovs-port") {
            let nm_ovs_iface_conns = get_nm_ovs_iface_conns(nm_conn, nm_conns);
            match nm_ovs_iface_conns.len() {
                d if d > 1 => {
                    if let Some(p) = get_ovs_port_config_for_bond(
                        nm_conn,
                        &nm_ovs_iface_conns,
                    ) {
                        ret.push(p);
                    }
                }
                1 => {
                    if let Some(p) = get_ovs_port_config_for_iface(
                        nm_conn,
                        nm_ovs_iface_conns[0],
                    ) {
                        ret.push(p);
                    }
                }
                _ => (),
            };
        }
    }
    ret
}

fn get_ovs_port_config_for_bond(
    nm_ovs_port_conn: &NmConnection,
    nm_ovs_iface_conns: &[&NmConnection],
) -> Option<OvsBridgePortConfig> {
    let mut port_conf = OvsBridgePortConfig::new();
    if let Some(n) = nm_ovs_port_conn.iface_name() {
        port_conf.name = n.to_string();
    } else {
        return None;
    }
    let mut ovs_bond_conf = OvsBridgeBondConfig::new();

    let nm_port_set = if let Some(s) = &nm_ovs_port_conn.ovs_port {
        s
    } else {
        return None;
    };

    ovs_bond_conf.mode = nm_port_set.mode.as_ref().and_then(|nm_mode| {
        if let Ok(m) = OvsBridgeBondMode::try_from(nm_mode.as_str()) {
            Some(m)
        } else {
            log::warn!("Unsupported OVS bond mode {}", nm_mode);
            None
        }
    });
    if ovs_bond_conf.mode.is_none()
        && nm_port_set.lacp.as_deref() == Some("active")
    {
        ovs_bond_conf.mode = Some(OvsBridgeBondMode::Lacp);
    }

    if ovs_bond_conf.mode.is_none() {
        ovs_bond_conf.mode = Some(OvsBridgeBondMode::ActiveBackup);
    }

    ovs_bond_conf.bond_downdelay = nm_port_set.down_delay;
    ovs_bond_conf.bond_updelay = nm_port_set.up_delay;
    let mut ovs_iface_confs = Vec::new();

    for nm_ovs_iface_conn in nm_ovs_iface_conns {
        if let Some(name) = nm_ovs_iface_conn.iface_name() {
            ovs_iface_confs.push(OvsBridgeBondPortConfig {
                name: name.to_string(),
            })
        }
    }

    ovs_bond_conf.ports = Some(ovs_iface_confs);
    port_conf.bond = Some(ovs_bond_conf);
    port_conf.vlan = get_vlan_info(nm_ovs_port_conn);

    Some(port_conf)
}

fn get_ovs_port_config_for_iface(
    nm_port_conn: &NmConnection,
    nm_iface_conn: &NmConnection,
) -> Option<OvsBridgePortConfig> {
    if let Some(name) = nm_iface_conn.iface_name() {
        let mut port_conf = OvsBridgePortConfig::new();
        port_conf.name = name.to_string();
        port_conf.vlan = get_vlan_info(nm_port_conn);
        Some(port_conf)
    } else {
        None
    }
}

fn get_nm_ovs_iface_conns<'a>(
    nm_ovs_port_conn: &'a NmConnection,
    nm_conns: &'a [&'a NmConnection],
) -> Vec<&'a NmConnection> {
    let mut ret = Vec::new();
    let uuid = if let Some(n) = nm_ovs_port_conn.uuid() {
        n
    } else {
        return ret;
    };
    let name = if let Some(n) = nm_ovs_port_conn.iface_name() {
        n
    } else {
        return ret;
    };
    for nm_conn in nm_conns {
        if nm_conn.controller_type() == Some("ovs-port")
            && (nm_conn.controller() == Some(uuid)
                || nm_conn.controller() == Some(name))
        {
            ret.push(nm_conn)
        }
    }
    ret
}

fn get_vlan_info(nm_conn: &NmConnection) -> Option<BridgePortVlanConfig> {
    if let Some(port_conf) = nm_conn.ovs_port.as_ref() {
        if let (Some(tag), Some(mode)) =
            (port_conf.tag, port_conf.vlan_mode.as_deref())
        {
            return Some(BridgePortVlanConfig {
                mode: Some(match mode {
                    "access" => BridgePortVlanMode::Access,
                    "trunk" => BridgePortVlanMode::Trunk,
                    _ => {
                        log::warn!("Unsupported OVS port VLAN mode {}", mode);
                        return None;
                    }
                }),
                tag: Some(match u16::try_from(tag) {
                    Ok(t) => t,
                    Err(_) => {
                        log::warn!(
                            "OVS port VLAN tag exceeded max u16 {}",
                            tag
                        );
                        return None;
                    }
                }),
                ..Default::default()
            });
        }
    }
    None
}

pub(crate) fn get_ovs_patch_config(
    nm_conn: &NmConnection,
) -> Option<OvsPatchConfig> {
    if let Some(nm_ovs_patch_set) = nm_conn.ovs_patch.as_ref() {
        if let Some(peer) = nm_ovs_patch_set.peer.as_deref() {
            return Some(OvsPatchConfig {
                peer: peer.to_string(),
            });
        }
    }
    None
}

pub(crate) fn get_ovs_dpdk_config(
    nm_conn: &NmConnection,
) -> Option<OvsDpdkConfig> {
    if let Some(nm_ovs_dpdk_set) = nm_conn.ovs_dpdk.as_ref() {
        if let Some(devargs) = nm_ovs_dpdk_set.devargs.as_deref() {
            return Some(OvsDpdkConfig {
                devargs: devargs.to_string(),
                rx_queue: nm_ovs_dpdk_set.n_rxq,
            });
        }
    }
    None
}

// When OVS system interface got detached from OVS bridge, we should remove its
// ovs port also.
pub(crate) fn get_orphan_ovs_port_uuids<'a>(
    ifaces: &Interfaces,
    cur_ifaces: &Interfaces,
    exist_nm_conns: &'a [NmConnection],
) -> Vec<&'a str> {
    let mut ret = Vec::new();
    for iface in ifaces.kernel_ifaces.values().filter(|i| {
        i.base_iface().controller_type.is_some()
            && i.base_iface().controller_type.as_ref()
                != Some(&InterfaceType::OvsBridge)
            && iface_was_ovs_sys_iface(i, cur_ifaces)
    }) {
        if let Some(exist_profile) = get_exist_profile(
            exist_nm_conns,
            iface.name(),
            &iface.iface_type(),
            &Vec::new(),
        ) {
            if exist_profile
                .connection
                .as_ref()
                .and_then(|c| c.controller_type.as_ref())
                == Some(&NM_SETTING_OVS_PORT_SETTING_NAME.to_string())
            {
                if let Some(parent) = exist_profile
                    .connection
                    .as_ref()
                    .and_then(|c| c.controller.as_ref())
                {
                    // We only touch port profiles created by nmstate which is
                    // using UUID for parent reference.
                    if uuid::Uuid::parse_str(parent).is_ok() {
                        log::info!(
                            "Deleting orphan OVS port connection {} \
                            as interface {}({}) detached from OVS bridge",
                            parent,
                            iface.name(),
                            iface.iface_type()
                        );
                        ret.push(parent.as_str())
                    }
                }
            }
        }
    }
    ret
}

fn iface_was_ovs_sys_iface(iface: &Interface, cur_ifaces: &Interfaces) -> bool {
    cur_ifaces.kernel_ifaces.get(iface.name()).map(|i| {
        i.base_iface().controller_type == Some(InterfaceType::OvsBridge)
    }) == Some(true)
}
