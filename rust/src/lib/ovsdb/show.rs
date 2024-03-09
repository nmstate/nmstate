// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde_json::Value;

use crate::{
    BridgePortTrunkTag, BridgePortVlanConfig, BridgePortVlanMode,
    BridgePortVlanRange, Interface, InterfaceType, Interfaces, NetworkState,
    NmstateError, OvsBridgeBondConfig, OvsBridgeBondMode,
    OvsBridgeBondPortConfig, OvsBridgeConfig, OvsBridgeInterface,
    OvsBridgeOptions, OvsBridgePortConfig, OvsBridgeStpOptions,
    OvsDbIfaceConfig, OvsDpdkConfig, OvsInterface, OvsPatchConfig,
    UnknownInterface,
};

use super::db::{parse_str_map, OvsDbConnection, OvsDbEntry};

pub(crate) fn ovsdb_is_running() -> bool {
    if let Ok(mut cli) = OvsDbConnection::new() {
        cli.check_connection()
    } else {
        false
    }
}

pub(crate) fn ovsdb_retrieve() -> Result<NetworkState, NmstateError> {
    let mut ret = NetworkState::new();
    let mut cli = OvsDbConnection::new()?;
    let ovsdb_ifaces = cli.get_ovs_ifaces()?;
    let ovsdb_brs = cli.get_ovs_bridges()?;
    let ovsdb_ports = cli.get_ovs_ports()?;

    for ovsdb_br in ovsdb_brs.values() {
        let mut iface = OvsBridgeInterface::new();
        iface.base.name = ovsdb_br.name.to_string();
        let external_ids = HashMap::from_iter(
            ovsdb_br
                .external_ids
                .clone()
                .drain()
                .map(|(k, v)| (k, Some(v))),
        );
        let other_config = HashMap::from_iter(
            ovsdb_br
                .other_config
                .clone()
                .drain()
                .map(|(k, v)| (k, Some(v))),
        );
        iface.base.ovsdb = Some(OvsDbIfaceConfig {
            external_ids: Some(external_ids),
            other_config: Some(other_config),
        });
        iface.bridge =
            Some(parse_ovs_bridge_conf(ovsdb_br, &ovsdb_ports, &ovsdb_ifaces));
        ret.append_interface_data(Interface::OvsBridge(iface));
    }

    for ovsdb_iface in ovsdb_ifaces.values() {
        if let Some(iface) =
            ovsdb_iface_to_nmstate(ovsdb_iface, &ret.interfaces)
        {
            ret.append_interface_data(iface);
        }
    }

    ret.ovsdb = Some(cli.get_ovsdb_global_conf()?);

    Ok(ret)
}

fn parse_ovs_bridge_conf(
    ovsdb_br: &OvsDbEntry,
    ovsdb_ports: &HashMap<String, OvsDbEntry>,
    ovsdb_ifaces: &HashMap<String, OvsDbEntry>,
) -> OvsBridgeConfig {
    let mut ret = OvsBridgeConfig::new();
    let mut port_confs = Vec::new();
    for port_uuid in ovsdb_br.ports.as_slice() {
        if let Some(ovsdb_port) = ovsdb_ports.get(port_uuid) {
            let mut port_conf = OvsBridgePortConfig::new();
            port_conf.name.clone_from(&ovsdb_port.name);
            if ovsdb_port.ports.len() > 1 {
                port_conf.bond =
                    Some(parse_ovs_bond_conf(ovsdb_port, ovsdb_ifaces));
            }
            port_conf.vlan = parse_ovs_vlan_conf(ovsdb_port);
            port_confs.push(port_conf);
        }
    }
    ret.options = Some(parse_ovs_bridge_options(&ovsdb_br.options));
    port_confs.sort_unstable_by(|a, b| {
        (a.bond.is_some(), a.name.as_str())
            .cmp(&(b.bond.is_some(), b.name.as_str()))
    });
    ret.ports = Some(port_confs);
    ret
}

fn parse_ovs_bridge_options(
    ovsdb_opts: &HashMap<String, Value>,
) -> OvsBridgeOptions {
    let mut ret = OvsBridgeOptions::new();
    if let Some(Value::String(v)) = ovsdb_opts.get("fail_mode") {
        ret.fail_mode = Some(v.to_string());
    } else {
        ret.fail_mode = Some(String::new());
    }
    if let Some(Value::Bool(v)) = ovsdb_opts.get("stp_enable") {
        ret.stp = Some(OvsBridgeStpOptions::new_enabled(*v))
    }
    if let Some(Value::Bool(v)) = ovsdb_opts.get("rstp_enable") {
        ret.rstp = Some(*v)
    }
    if let Some(Value::Bool(v)) = ovsdb_opts.get("mcast_snooping_enable") {
        ret.mcast_snooping_enable = Some(*v)
    }
    if let Some(Value::String(v)) = ovsdb_opts.get("datapath_type") {
        ret.datapath = Some(v.to_string())
    }
    ret
}

fn parse_ovs_bond_conf(
    ovsdb_port: &OvsDbEntry,
    ovsdb_ifaces: &HashMap<String, OvsDbEntry>,
) -> OvsBridgeBondConfig {
    let mut bond_conf = OvsBridgeBondConfig::new();
    let mut bond_port_confs = Vec::new();
    for bond_port_uuid in ovsdb_port.ports.as_slice() {
        if let Some(ovsdb_iface) = ovsdb_ifaces.get(bond_port_uuid) {
            bond_port_confs.push(OvsBridgeBondPortConfig {
                name: ovsdb_iface.name.to_string(),
            });
        }
    }
    bond_port_confs
        .sort_unstable_by(|a, b| a.name.as_str().cmp(b.name.as_str()));
    if let Some(Value::String(bond_mode)) = ovsdb_port.options.get("bond_mode")
    {
        match bond_mode.as_str() {
            "active-backup" => {
                bond_conf.mode = Some(OvsBridgeBondMode::ActiveBackup)
            }
            "balance-slb" => {
                bond_conf.mode = Some(OvsBridgeBondMode::BalanceSlb)
            }
            "balance-tcp" => {
                bond_conf.mode = Some(OvsBridgeBondMode::BalanceTcp)
            }
            v => {
                log::warn!("Unknown OVS bond mode {v}");
            }
        }
    }

    if bond_conf.mode.is_none() {
        if let Some(Value::String(lacp)) = ovsdb_port.options.get("lacp") {
            if lacp.as_str() == "active" {
                bond_conf.mode = Some(OvsBridgeBondMode::Lacp);
            }
        }
    }

    if let Some(Value::Number(v)) = ovsdb_port.options.get("bond_updelay") {
        if let Some(v) = v.as_u64() {
            bond_conf.bond_updelay = if v == 0 { None } else { Some(v as u32) };
        }
    }
    if let Some(Value::Number(v)) = ovsdb_port.options.get("bond_downdelay") {
        if let Some(v) = v.as_u64() {
            bond_conf.bond_downdelay =
                if v == 0 { None } else { Some(v as u32) };
        }
    }
    let external_ids = HashMap::from_iter(
        ovsdb_port
            .external_ids
            .clone()
            .drain()
            .map(|(k, v)| (k, Some(v))),
    );

    let other_config = HashMap::from_iter(
        ovsdb_port
            .other_config
            .clone()
            .drain()
            .map(|(k, v)| (k, Some(v))),
    );
    if !external_ids.is_empty() || !other_config.is_empty() {
        bond_conf.ovsdb = Some(OvsDbIfaceConfig {
            external_ids: Some(external_ids),
            other_config: Some(other_config),
        });
    }

    bond_conf.ports = Some(bond_port_confs);
    bond_conf
}

fn parse_ovs_vlan_conf(
    ovsdb_port: &OvsDbEntry,
) -> Option<BridgePortVlanConfig> {
    if let Some(Value::String(mode)) = ovsdb_port.options.get("vlan_mode") {
        let mut ret = BridgePortVlanConfig::new();
        let mode = match mode.as_str() {
            "access" => BridgePortVlanMode::Access,
            "trunk" => BridgePortVlanMode::Trunk,
            _ => {
                log::warn!("Unknown OVS VLAN mode {mode}");
                return None;
            }
        };
        ret.mode = Some(mode);
        if let Some(Value::Number(vlan_id)) = ovsdb_port.options.get("tag") {
            ret.tag = vlan_id.as_u64().map(|t| t as u16);
            if mode == BridgePortVlanMode::Trunk {
                ret.enable_native = Some(true);
            }
        }
        if ret.tag.is_none() {
            ret.tag = Some(0);
        }
        if mode == BridgePortVlanMode::Trunk {
            if let Some(Value::Array(trunk_tags)) =
                ovsdb_port.options.get("trunks")
            {
                if let Some(Value::Array(trunk_tags)) = trunk_tags.get(1) {
                    ret.trunk_tags = Some(compress_vlan_trunk_tags(trunk_tags));
                }
            } else if let Some(Value::Number(trunk_tag)) =
                ovsdb_port.options.get("trunks")
            {
                if let Some(tag) = trunk_tag.as_u64() {
                    ret.trunk_tags =
                        Some(vec![BridgePortTrunkTag::Id(tag as u16)]);
                }
            }
        }
        Some(ret)
    } else {
        None
    }
}

fn compress_vlan_trunk_tags(tags: &[Value]) -> Vec<BridgePortTrunkTag> {
    let mut ranges: Vec<BridgePortVlanRange> = Vec::new();
    for tag in tags {
        if let Value::Number(tag) = tag {
            let tag = if let Some(tag) = tag.as_u64() {
                tag as u16
            } else {
                continue;
            };
            let mut found_match = false;
            for exist_range in &mut ranges {
                if tag == exist_range.min - 1 {
                    exist_range.min -= 1;
                    found_match = true;
                    break;
                }
                if tag == exist_range.max + 1 {
                    exist_range.max += 1;
                    found_match = true;
                    break;
                }
            }
            if !found_match {
                ranges.push(BridgePortVlanRange { min: tag, max: tag });
            }
        }
    }

    let mut ret = Vec::new();
    for range in ranges {
        if range.min == range.max {
            ret.push(BridgePortTrunkTag::Id(range.min))
        } else {
            ret.push(BridgePortTrunkTag::IdRange(range))
        }
    }

    ret
}

fn parse_ovs_patch_conf(ovsdb_iface: &OvsDbEntry) -> Option<OvsPatchConfig> {
    if let Some(Value::Array(v)) = ovsdb_iface.options.get("options") {
        let options = parse_str_map(v);
        if let Some(peer) = options.get("peer") {
            return Some(OvsPatchConfig {
                peer: peer.to_string(),
            });
        }
    }
    None
}

fn parse_ovs_iface_dpdk_conf(
    ovsdb_iface: &OvsDbEntry,
) -> Option<OvsDpdkConfig> {
    if let Some(Value::Array(v)) = ovsdb_iface.options.get("options") {
        let options = parse_str_map(v);
        if let Some(devargs) = options.get("dpdk-devargs") {
            let mut conf = OvsDpdkConfig {
                devargs: devargs.to_string(),
                ..Default::default()
            };
            if let Some(n_rxq) = options.get("n_rxq") {
                if let Ok(i) = n_rxq.parse::<u32>() {
                    conf.rx_queue = Some(i)
                }
            }
            if let Some(n_rxq_desc) = options.get("n_rxq_desc") {
                if let Ok(i) = n_rxq_desc.parse::<u32>() {
                    conf.n_rxq_desc = Some(i)
                }
            }
            if let Some(n_txq_desc) = options.get("n_txq_desc") {
                if let Ok(i) = n_txq_desc.parse::<u32>() {
                    conf.n_txq_desc = Some(i)
                }
            }
            return Some(conf);
        }
    }
    None
}

fn ovsdb_iface_to_nmstate(
    ovsdb_iface: &OvsDbEntry,
    ifaces: &Interfaces,
) -> Option<Interface> {
    let mut port_to_ctrl = HashMap::new();
    for iface in ifaces
        .user_ifaces
        .values()
        .filter(|i| i.iface_type() == InterfaceType::OvsBridge)
    {
        if let Some(ports) = iface.ports() {
            for port in ports {
                port_to_ctrl.insert(port, iface.name());
            }
        }
    }

    let mut iface = match ovsdb_iface.iface_type.as_str() {
        "system" => Interface::Unknown(UnknownInterface::new()),
        "internal" => Interface::OvsInterface(OvsInterface::new()),
        "patch" => {
            let mut ovs_iface = OvsInterface::new();
            ovs_iface.patch = parse_ovs_patch_conf(ovsdb_iface);
            Interface::OvsInterface(ovs_iface)
        }
        "dpdk" => {
            let mut ovs_iface = OvsInterface::new();
            ovs_iface.dpdk = parse_ovs_iface_dpdk_conf(ovsdb_iface);
            // DPDK interface does not have kernel representative, the MTU is
            // set in ovsdb.
            ovs_iface.base.mtu = get_dpdk_mtu(ovsdb_iface);
            Interface::OvsInterface(ovs_iface)
        }
        i => {
            log::warn!("Unknown OVS interface type {i}");
            return None;
        }
    };
    iface.base_iface_mut().name = ovsdb_iface.name.to_string();

    if let Some(ctrl) = port_to_ctrl.get(&iface.name()) {
        iface.base_iface_mut().controller = Some(ctrl.to_string());
        iface.base_iface_mut().controller_type = Some(InterfaceType::OvsBridge);
    }

    let external_ids = HashMap::from_iter(
        ovsdb_iface
            .external_ids
            .clone()
            .drain()
            .map(|(k, v)| (k, Some(v))),
    );
    let other_config = HashMap::from_iter(
        ovsdb_iface
            .other_config
            .clone()
            .drain()
            .map(|(k, v)| (k, Some(v))),
    );
    if !external_ids.is_empty() || !other_config.is_empty() {
        iface.base_iface_mut().ovsdb = Some(OvsDbIfaceConfig {
            external_ids: Some(external_ids),
            other_config: Some(other_config),
        });
    }
    Some(iface)
}

fn get_dpdk_mtu(ovsdb_iface: &OvsDbEntry) -> Option<u64> {
    if let Some(Value::Number(v)) = ovsdb_iface.options.get("mtu") {
        v.as_u64()
    } else {
        None
    }
}
