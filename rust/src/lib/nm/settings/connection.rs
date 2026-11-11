// SPDX-License-Identifier: Apache-2.0

use super::{
    super::{
        NmConnectionMatcher,
        nm_dbus::{
            NmConnection, NmIfaceType, NmSettingConnection, NmSettingMacVlan,
            NmSettingVeth, NmSettingVrf, NmSettingVxlan,
            NmSettingsConnectionFlag,
        },
    },
    bond::{gen_nm_bond_port_setting, gen_nm_bond_setting},
    bridge::{gen_nm_br_port_setting, gen_nm_br_setting},
    ethtool::gen_ethtool_setting,
    hsr::gen_nm_hsr_setting,
    ieee8021x::gen_nm_802_1x_setting,
    iface_match::apply_iface_match,
    infiniband::gen_nm_ib_setting,
    ip::gen_nm_ip_setting,
    ip_tunnel::gen_nm_ip_tunnel_setting,
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
    veth::create_veth_peer_connection_if_not_found,
    vlan::gen_nm_vlan_setting,
    vpn::gen_nm_ipsec_vpn_setting,
    wired::gen_nm_wired_setting,
};
use crate::{
    BaseInterface, Interface, InterfaceIdentifier, InterfaceType,
    MergedInterface, MergedNetworkState, NmstateError, OvsBridgePortConfig,
};

pub(crate) fn iface_to_nm_connections(
    merged_iface: &MergedInterface,
    merged_state: &MergedNetworkState,
    conn_matcher: &NmConnectionMatcher,
    gen_conf_mode: bool,
) -> Result<Vec<NmConnection>, NmstateError> {
    let mut ret: Vec<NmConnection> = Vec::new();

    let mut iface = if let Some(i) = merged_iface.for_apply.as_ref() {
        i.clone()
    } else {
        return Ok(ret);
    };

    let exist_nm_conn = if merged_state.override_iface {
        None
    } else {
        conn_matcher.get_prefered_saved(iface.base_iface())
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
                        conn_matcher,
                        gen_conf_mode,
                    );
                }
            }
            // We should not return multi-connect NmConnection
            if !nm_conn.is_multi_connect() {
                return Ok(vec![nm_conn.clone()]);
            }
        } else if !iface.is_userspace() {
            // User want to convert unmanaged interface to managed
            if let Some(cur_iface) = merged_iface.current.as_ref()
                && cur_iface.is_ignore()
            {
                return persisten_iface_cur_conf(
                    cur_iface,
                    merged_state,
                    conn_matcher,
                    gen_conf_mode,
                );
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

    if !merged_state.override_iface
        && let Some(applied) = conn_matcher
            .get_applied(iface.base_iface())
            .filter(|applied| {
                exist_nm_conn.is_none_or(|saved| saved.uuid() == applied.uuid())
            })
    {
        preserve_applied_inverted_rules(
            &mut nm_conn,
            applied,
            iface.base_iface(),
        );
    }

    // If existing NmConnection is a multi-connect one, we should
    // generate new NmSettingConnection (UUID, name and etc)
    if nm_conn.is_multi_connect() {
        nm_conn.connection = None;
        nm_conn.obj_path = String::new();
    }

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
                let exist_nm_ovs_port_conn = conn_matcher
                    .get_prefered_saved_by_name_type(
                        &ovs_port_conf.name,
                        &NmIfaceType::OvsPort,
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
                    ret.push(create_veth_peer_connection_if_not_found(
                        veth_conf.peer.as_str(),
                        eth_iface.base.name.as_str(),
                        conn_matcher,
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
        Interface::IpTunnel(iface) => {
            gen_nm_ip_tunnel_setting(iface, &mut nm_conn);
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

    if nm_conn.controller_type() != Some(&NmIfaceType::OvsPort)
        && nm_conn.iface_type() != Some(&NmIfaceType::OvsIface)
    {
        nm_conn.ovs_iface = None;
    }

    if let (Some(ctrl), Some(ctrl_type)) = (
        iface.base_iface().controller.as_ref(),
        iface.base_iface().controller_type.as_ref(),
    ) && let Some(ctrl_iface) =
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
                        != merged_iface
                            .current
                            .as_ref()
                            .and_then(|i| i.base_iface().controller.as_ref())
                {
                    let exist_nm_ovs_port_conn = conn_matcher
                        .get_prefered_saved_by_name_type(
                            &ovs_port_name,
                            &NmIfaceType::OvsPort,
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

    // When detaching a OVS system interface from OVS bridge, we should remove
    // its NmSettingOvsIface setting
    if iface.base_iface().controller.as_deref() == Some("") {
        nm_conn.ovs_iface = None;
    }

    ret.insert(0, nm_conn);

    Ok(ret)
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
            Some(NmIfaceType::from(&iface.iface_type()));
        if let Interface::Ethernet(eth_iface) = iface
            && eth_iface.veth.is_some()
        {
            new_nm_conn_set.iface_type = Some(NmIfaceType::Veth);
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
        .map(NmIfaceType::from);
    let ctrl_name = iface.base_iface().controller.as_deref();
    if let Some(ctrl_name) = ctrl_name {
        if ctrl_name.is_empty() || nm_ctrl_type == Some(NmIfaceType::Hsr) {
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

    apply_iface_match(nm_conn, iface.base_iface());

    nm_conn.connection = Some(nm_conn_set);

    Ok(())
}

pub(crate) fn uuid_from_name_and_type(
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

fn persisten_iface_cur_conf(
    cur_iface: &Interface,
    merged_state: &MergedNetworkState,
    conn_matcher: &NmConnectionMatcher,
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
        conn_matcher,
        gen_conf_mode,
    )
}

fn preserve_applied_inverted_rules(
    saved: &mut NmConnection,
    applied: &NmConnection,
    iface: &BaseInterface,
) {
    for (rules_changed, saved_ip, applied_ip) in [
        (
            iface.ipv4.as_ref().is_some_and(|ip| ip.rules.is_some()),
            &mut saved.ipv4,
            &applied.ipv4,
        ),
        (
            iface.ipv6.as_ref().is_some_and(|ip| ip.rules.is_some()),
            &mut saved.ipv6,
            &applied.ipv6,
        ),
    ] {
        if rules_changed
            && let Some(applied_ip) = applied_ip
            && (applied_ip.route_rules.iter().any(|rule| rule.is_inverted())
                || saved_ip.as_ref().is_some_and(|ip| {
                    ip.route_rules.iter().any(|rule| rule.is_inverted())
                }))
        {
            saved_ip
                .get_or_insert_with(Default::default)
                .route_rules
                .clone_from(&applied_ip.route_rules);
        }
    }
}

fn preserve_current_ip(iface: &mut Interface, cur_iface: Option<&Interface>) {
    if iface.base_iface().ipv4.is_none() {
        iface.base_iface_mut().ipv4 =
            cur_iface.as_ref().and_then(|i| i.base_iface().ipv4.clone());
        if let Some(addrs) = iface
            .base_iface_mut()
            .ipv4
            .as_mut()
            .and_then(|ip| ip.addresses.as_mut())
        {
            addrs.retain(|addr| !addr.is_protocol_other())
        }
    }
    if iface.base_iface().ipv6.is_none() {
        iface.base_iface_mut().ipv6 =
            cur_iface.as_ref().and_then(|i| i.base_iface().ipv6.clone());
        if let Some(addrs) = iface
            .base_iface_mut()
            .ipv6
            .as_mut()
            .and_then(|ip| ip.addresses.as_mut())
        {
            addrs.retain(|addr| !addr.is_protocol_other())
        }
    }
}

#[cfg(all(test, feature = "query_apply"))]
mod tests {
    use std::collections::{HashMap, HashSet};

    use super::*;
    use crate::{
        NetworkState, RouteRuleEntry, RouteRuleState,
        nm::{
            nm_dbus::{
                NmActiveConnection, NmIpRouteRule, NmSettingIp,
                NmSettingIpMethod,
            },
            query_apply::{
                nm_ip_setting_to_nmstate4, nm_ip_setting_to_nmstate6,
            },
            route_rule::{nm_rule_to_nmstate, store_route_rule_config},
        },
    };

    fn raw_rule(is_ipv6: bool, index: u8, inverted: bool) -> NmIpRouteRule {
        let address = if is_ipv6 {
            format!("2001:db8::{index}")
        } else {
            format!("192.0.2.{index}")
        };
        let mut raw: HashMap<String, zvariant::OwnedValue> = [
            (
                "family",
                zvariant::Value::new(if is_ipv6 { 10i32 } else { 2 }),
            ),
            ("priority", zvariant::Value::new(100u32)),
            ("from", zvariant::Value::new(address)),
            (
                "from-len",
                zvariant::Value::new(if is_ipv6 { 128u8 } else { 32 }),
            ),
            ("table", zvariant::Value::new(500u32)),
            ("iifname", zvariant::Value::new("eth1")),
        ]
        .into_iter()
        .map(|(key, value)| (key.to_string(), value.try_into().unwrap()))
        .collect();
        if inverted {
            for (key, value) in [
                ("invert", zvariant::Value::new(true)),
                ("oifname", zvariant::Value::new("dummy99")),
            ] {
                raw.insert(key.to_string(), value.try_into().unwrap());
            }
        }
        NmIpRouteRule::try_from(raw).unwrap()
    }

    fn connection(inverted: Option<u8>, last: u8) -> NmConnection {
        let mut conn = NmConnection::default();
        let mut setting = NmSettingConnection::default();
        setting.id = Some("eth1".to_string());
        setting.iface_name = Some("eth1".to_string());
        setting.iface_type = Some(NmIfaceType::Ethernet);
        setting.uuid = Some("a35a9e38-027b-4b15-866d-e48143783bf3".to_string());
        conn.connection = Some(setting);
        for (is_ipv6, ip) in [(false, &mut conn.ipv4), (true, &mut conn.ipv6)] {
            let mut setting = NmSettingIp::default();
            setting.method = Some(NmSettingIpMethod::Auto);
            setting.route_rules.push(raw_rule(is_ipv6, 1, false));
            if let Some(index) = inverted {
                setting.route_rules.push(raw_rule(is_ipv6, index, true));
            }
            setting.route_rules.push(raw_rule(is_ipv6, last, false));
            *ip = Some(setting);
        }
        conn
    }

    fn ip_setting(conn: &NmConnection, is_ipv6: bool) -> &NmSettingIp {
        if is_ipv6 { &conn.ipv6 } else { &conn.ipv4 }
            .as_ref()
            .unwrap()
    }

    fn generate_connection(
        desired: NetworkState,
        saved: &NmConnection,
        applied: &NmConnection,
    ) -> (NmConnection, MergedNetworkState) {
        let mut iface: Interface = serde_yaml::from_str(
            "name: eth1\ntype: ethernet\nstate: up\nmtu: 1500",
        )
        .unwrap();
        iface.base_iface_mut().ipv4 =
            Some(nm_ip_setting_to_nmstate4(applied.ipv4.as_ref().unwrap()));
        iface.base_iface_mut().ipv6 = Some(nm_ip_setting_to_nmstate6(
            "eth1",
            &InterfaceType::Ethernet,
            applied.ipv6.as_ref().unwrap(),
        ));
        let mut current = NetworkState::new();
        current.interfaces.push(iface);
        current.rules.config = Some(
            [false, true]
                .into_iter()
                .flat_map(|is_ipv6| {
                    ip_setting(applied, is_ipv6).route_rules.iter().filter_map(
                        move |rule| nm_rule_to_nmstate(is_ipv6, rule),
                    )
                })
                .collect(),
        );
        let mut merged = MergedNetworkState::new(
            desired,
            current,
            Default::default(),
            false,
        )
        .unwrap();
        store_route_rule_config(&mut merged).unwrap();
        let matcher = NmConnectionMatcher::new(
            vec![saved.clone()],
            vec![applied.clone()],
            vec![NmActiveConnection {
                uuid: applied.uuid().unwrap().to_string(),
                iface_type: NmIfaceType::Ethernet,
                iface_name: "eth1".to_string(),
                state: NmActiveConnection::STATE_ACTIVATED,
                ..Default::default()
            }],
            &merged.interfaces,
        );
        let mut connections = iface_to_nm_connections(
            merged
                .interfaces
                .get_iface("eth1", InterfaceType::Ethernet)
                .unwrap(),
            &merged,
            &matcher,
            false,
        )
        .unwrap();
        assert_eq!(connections.len(), 1);
        (connections.remove(0), merged)
    }

    fn rules_for_apply(
        merged: &MergedNetworkState,
        is_ipv6: bool,
    ) -> Option<&HashSet<RouteRuleEntry>> {
        let base = merged
            .interfaces
            .get_iface("eth1", InterfaceType::Ethernet)
            .unwrap()
            .for_apply
            .as_ref()
            .unwrap()
            .base_iface();
        if is_ipv6 {
            base.ipv6.as_ref().and_then(|ip| ip.rules.as_ref())
        } else {
            base.ipv4.as_ref().and_then(|ip| ip.rules.as_ref())
        }
    }

    fn assert_saved_rules_preserved(desired: NetworkState) {
        for (saved_inverted, applied_inverted) in [
            (Some(2), Some(2)),
            (Some(4), Some(2)),
            (None, Some(2)),
            (Some(2), None),
        ] {
            let saved = connection(saved_inverted, 5);
            let applied = connection(applied_inverted, 3);
            let (result, merged) =
                generate_connection(desired.clone(), &saved, &applied);
            let desired_iface =
                desired.interfaces.kernel_ifaces["eth1"].base_iface();
            if let Some(mtu) = desired_iface.mtu {
                assert_eq!(
                    result.wired.as_ref().unwrap().mtu,
                    Some(u32::try_from(mtu).unwrap())
                );
            }
            for is_ipv6 in [false, true] {
                if (is_ipv6 && desired_iface.ipv6.is_some())
                    || (!is_ipv6 && desired_iface.ipv4.is_some())
                {
                    assert_eq!(
                        ip_setting(&result, is_ipv6).ignore_auto_dns,
                        Some(true)
                    );
                }
                assert!(rules_for_apply(&merged, is_ipv6).is_none());
                assert_eq!(
                    ip_setting(&result, is_ipv6).route_rules,
                    ip_setting(&saved, is_ipv6).route_rules
                );
            }
        }
    }

    #[test]
    fn test_mtu_change_preserves_saved_route_rules() {
        assert_saved_rules_preserved(
            serde_yaml::from_str("interfaces: [{name: eth1, mtu: 1400}]")
                .unwrap(),
        );
    }

    #[test]
    fn test_ip_change_preserves_saved_route_rules() {
        for family in ["ipv4", "ipv6"] {
            assert_saved_rules_preserved(
                serde_yaml::from_str(&format!(
                    "interfaces: [{{name: eth1, {family}: {{auto-dns: \
                     false}}}}]"
                ))
                .unwrap(),
            );
        }
    }

    #[test]
    fn test_rule_append_preserves_other_family_saved_rules() {
        for is_ipv6 in [false, true] {
            let saved = connection(Some(4), 5);
            let applied = connection(Some(2), 3);
            let added = raw_rule(is_ipv6, 6, false);
            let mut desired = NetworkState::new();
            desired.rules.config =
                Some(vec![nm_rule_to_nmstate(is_ipv6, &added).unwrap()]);
            let (result, merged) =
                generate_connection(desired, &saved, &applied);
            assert!(rules_for_apply(&merged, is_ipv6).is_some());
            assert!(rules_for_apply(&merged, !is_ipv6).is_none());
            let mut expected =
                ip_setting(&applied, is_ipv6).route_rules.clone();
            expected.push(added);
            assert_eq!(ip_setting(&result, is_ipv6).route_rules, expected);
            assert_eq!(
                ip_setting(&result, !is_ipv6).route_rules,
                ip_setting(&saved, !is_ipv6).route_rules
            );
        }
    }

    #[test]
    fn test_empty_rule_rebuild_preserves_only_applied_inverted_rules() {
        for is_ipv6 in [false, true] {
            for (saved_inverted, applied_inverted) in
                [(Some(4), Some(2)), (None, Some(2)), (Some(2), None)]
            {
                let saved = connection(saved_inverted, 5);
                let applied = connection(applied_inverted, 3);
                let mut desired = NetworkState::new();
                let mut absent =
                    nm_rule_to_nmstate(is_ipv6, &raw_rule(is_ipv6, 1, false))
                        .unwrap();
                absent.ip_from = None;
                absent.state = Some(RouteRuleState::Absent);
                desired.rules.config = Some(vec![absent]);
                let (result, merged) =
                    generate_connection(desired, &saved, &applied);
                assert!(rules_for_apply(&merged, is_ipv6).unwrap().is_empty());
                let expected: Vec<_> = applied_inverted
                    .map(|index| raw_rule(is_ipv6, index, true))
                    .into_iter()
                    .collect();
                assert_eq!(ip_setting(&result, is_ipv6).route_rules, expected);
            }
        }
    }
}
