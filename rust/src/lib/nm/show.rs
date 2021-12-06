use std::collections::HashMap;

use log::{debug, warn};
use nm_dbus::{
    NmActiveConnection, NmApi, NmConnection, NmDeviceState, NmSettingIp,
    NmSettingIpMethod,
};

use crate::{
    nm::active_connection::create_index_for_nm_acs_by_name_type,
    nm::connection::{
        create_index_for_nm_conns_by_ctrler_type,
        create_index_for_nm_conns_by_name_type, get_port_nm_conns,
        NM_SETTING_BRIDGE_SETTING_NAME, NM_SETTING_OVS_BRIDGE_SETTING_NAME,
        NM_SETTING_OVS_IFACE_SETTING_NAME, NM_SETTING_VETH_SETTING_NAME,
        NM_SETTING_WIRED_SETTING_NAME,
    },
    nm::error::nm_error_to_nmstate,
    nm::ovs::nm_ovs_bridge_conf_get,
    BaseInterface, EthernetInterface, Interface, InterfaceIpv4, InterfaceIpv6,
    InterfaceState, InterfaceType, Interfaces, LinuxBridgeInterface,
    NetworkState, NmstateError, OvsBridgeInterface, OvsInterface,
    UnknownInterface,
};

pub(crate) fn nm_retrieve() -> Result<NetworkState, NmstateError> {
    let mut net_state = NetworkState::new();
    net_state.prop_list = vec!["interfaces"];
    let nm_api = NmApi::new().map_err(nm_error_to_nmstate)?;
    let nm_conns = nm_api
        .applied_connections_get()
        .map_err(nm_error_to_nmstate)?;
    let nm_devs = nm_api.devices_get().map_err(nm_error_to_nmstate)?;
    let nm_saved_conns =
        nm_api.connections_get().map_err(nm_error_to_nmstate)?;
    let nm_acs = nm_api
        .active_connections_get()
        .map_err(nm_error_to_nmstate)?;

    let nm_conns_name_type_index =
        create_index_for_nm_conns_by_name_type(nm_conns.as_slice());
    let mut nm_saved_conn_uuid_index: HashMap<&str, &NmConnection> =
        HashMap::new();
    for nm_saved_conn in nm_saved_conns.as_slice() {
        if let Some(uuid) = nm_saved_conn.uuid() {
            nm_saved_conn_uuid_index.insert(uuid, nm_saved_conn);
        }
    }
    let nm_saved_conns_ctrler_type_index =
        create_index_for_nm_conns_by_ctrler_type(nm_saved_conns.as_slice());
    let nm_acs_name_type_index =
        create_index_for_nm_acs_by_name_type(nm_acs.as_slice());

    // Include disconnected interface as state:down
    // This is used for verify on `state: absent`
    for nm_dev in &nm_devs {
        let iface_type = nm_iface_type_to_nmstate(&nm_dev.iface_type);
        match nm_dev.state {
            NmDeviceState::Unmanaged => continue,
            NmDeviceState::Disconnected => {
                let mut base_iface = BaseInterface::new();
                base_iface.name = nm_dev.name.clone();
                base_iface.prop_list = vec!["name", "iface_type", "state"];
                base_iface.state = InterfaceState::Down;
                base_iface.iface_type = iface_type;
                let iface = match &base_iface.iface_type {
                    InterfaceType::Ethernet => Interface::Ethernet({
                        let mut iface = EthernetInterface::new();
                        iface.base = base_iface;
                        iface
                    }),
                    InterfaceType::LinuxBridge => Interface::LinuxBridge({
                        let mut iface = LinuxBridgeInterface::new();
                        iface.base = base_iface;
                        iface
                    }),
                    InterfaceType::OvsInterface => Interface::OvsInterface({
                        let mut iface = OvsInterface::new();
                        iface.base = base_iface;
                        iface
                    }),
                    _ => Interface::Unknown({
                        let mut iface = UnknownInterface::new();
                        iface.base = base_iface;
                        iface
                    }),
                };
                debug!("Found disconnected interface {:?}", iface);
                net_state.append_interface_data(iface);
            }
            _ => {
                let nm_conn = if let Some(c) = get_first_nm_conn(
                    &nm_conns_name_type_index,
                    &nm_dev.name,
                    &nm_dev.iface_type,
                ) {
                    c
                } else {
                    warn!(
                        "Failed to find applied NmConnection for interface \
                        {} {}",
                        nm_dev.name, nm_dev.iface_type
                    );

                    continue;
                };
                let nm_ac = get_nm_ac(
                    &nm_acs_name_type_index,
                    &nm_dev.name,
                    &nm_dev.iface_type,
                );

                // NM developer confirmed NmActiveConnection UUID is the
                // UUID of NmConnection associated
                let nm_saved_conn = if let Some(nm_ac) = nm_ac {
                    nm_saved_conn_uuid_index.get(nm_ac.uuid.as_str()).copied()
                } else {
                    None
                };
                let port_saved_nm_conns = if iface_type.is_controller() {
                    Some(get_port_nm_conns(
                        nm_conn,
                        &nm_saved_conns_ctrler_type_index,
                    ))
                } else {
                    None
                };

                if let Some(iface) = iface_get(
                    nm_conn,
                    nm_saved_conn,
                    port_saved_nm_conns.as_ref().map(Vec::as_ref),
                ) {
                    debug!("Found interface {:?}", iface);
                    net_state.append_interface_data(iface);
                }
            }
        }
    }

    set_ovs_iface_controller_info(&mut net_state.interfaces);

    Ok(net_state)
}

fn nm_iface_type_to_nmstate(nm_iface_type: &str) -> InterfaceType {
    match nm_iface_type {
        NM_SETTING_WIRED_SETTING_NAME => InterfaceType::Ethernet,
        NM_SETTING_VETH_SETTING_NAME => InterfaceType::Ethernet,
        NM_SETTING_BRIDGE_SETTING_NAME => InterfaceType::LinuxBridge,
        NM_SETTING_OVS_BRIDGE_SETTING_NAME => InterfaceType::OvsBridge,
        NM_SETTING_OVS_IFACE_SETTING_NAME => InterfaceType::OvsInterface,
        _ => InterfaceType::Other(nm_iface_type.to_string()),
    }
}

fn nm_conn_to_base_iface(nm_conn: &NmConnection) -> Option<BaseInterface> {
    if let Some(iface_name) = nm_conn.iface_name() {
        if let Some(iface_type) = nm_conn.iface_type() {
            let ipv4 = nm_conn.ipv4.as_ref().map(|nm_ipv4_setting| {
                nm_ip_setting_to_nmstate4(nm_ipv4_setting)
            });
            let ipv6 = nm_conn.ipv6.as_ref().map(|nm_ipv6_setting| {
                nm_ip_setting_to_nmstate6(nm_ipv6_setting)
            });

            let mut base_iface = BaseInterface::new();
            base_iface.name = iface_name.to_string();
            base_iface.prop_list =
                vec!["name", "state", "iface_type", "ipv4", "ipv6"];
            base_iface.state = InterfaceState::Up;
            base_iface.iface_type = nm_iface_type_to_nmstate(iface_type);
            base_iface.ipv4 = ipv4;
            base_iface.ipv6 = ipv6;
            base_iface.controller = nm_conn.controller().map(|c| c.to_string());
            return Some(base_iface);
        }
    }
    None
}

fn nm_ip_setting_to_nmstate4(nm_ip_setting: &NmSettingIp) -> InterfaceIpv4 {
    if let Some(nm_ip_method) = &nm_ip_setting.method {
        let (enabled, dhcp) = match nm_ip_method {
            NmSettingIpMethod::Disabled => (false, false),
            NmSettingIpMethod::LinkLocal
            | NmSettingIpMethod::Manual
            | NmSettingIpMethod::Shared => (true, false),
            NmSettingIpMethod::Auto => (true, true),
            _ => {
                warn!("Unexpected NM IP method {:?}", nm_ip_method);
                (true, false)
            }
        };
        InterfaceIpv4 {
            enabled,
            dhcp,
            prop_list: vec!["enabled", "dhcp"],
            ..Default::default()
        }
    } else {
        InterfaceIpv4::default()
    }
}

fn nm_ip_setting_to_nmstate6(nm_ip_setting: &NmSettingIp) -> InterfaceIpv6 {
    if let Some(nm_ip_method) = &nm_ip_setting.method {
        let (enabled, dhcp, autoconf) = match nm_ip_method {
            NmSettingIpMethod::Disabled => (false, false, false),
            NmSettingIpMethod::LinkLocal
            | NmSettingIpMethod::Manual
            | NmSettingIpMethod::Shared => (true, false, false),
            NmSettingIpMethod::Auto => (true, true, true),
            NmSettingIpMethod::Dhcp => (true, true, false),
            NmSettingIpMethod::Ignore => (true, false, false),
        };
        InterfaceIpv6 {
            enabled,
            dhcp,
            autoconf,
            prop_list: vec!["enabled", "dhcp", "autoconf"],
            ..Default::default()
        }
    } else {
        InterfaceIpv6::default()
    }
}

// Applied connection does not hold OVS config, we need the NmConnection
// used by `NmActiveConnection` also.
fn iface_get(
    nm_conn: &NmConnection,
    nm_saved_conn: Option<&NmConnection>,
    port_saved_nm_conns: Option<&[&NmConnection]>,
) -> Option<Interface> {
    if let Some(base_iface) = nm_conn_to_base_iface(nm_conn) {
        let iface = match &base_iface.iface_type {
            InterfaceType::LinuxBridge => Interface::LinuxBridge({
                let mut iface = LinuxBridgeInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::Ethernet => Interface::Ethernet({
                let mut iface = EthernetInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::OvsInterface => Interface::OvsInterface({
                let mut iface = OvsInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::OvsBridge => {
                // NetworkManager applied connection does not
                // have ovs configure
                if let Some(nm_saved_conn) = nm_saved_conn {
                    let mut br_iface = OvsBridgeInterface::new();
                    br_iface.base = base_iface;
                    br_iface.bridge = nm_ovs_bridge_conf_get(
                        nm_saved_conn,
                        port_saved_nm_conns,
                    )
                    .ok();
                    Interface::OvsBridge(br_iface)
                } else {
                    warn!(
                        "Failed to get active connection of interface \
                        {} {}",
                        base_iface.name, base_iface.iface_type
                    );
                    return None;
                }
            }
            _ => {
                debug!("Skip unsupported interface {:?}", base_iface);
                return None;
            }
        };
        debug!("Found interface {:?}", iface);
        Some(iface)
    } else {
        // NmConnection has no interface name
        None
    }
}

fn get_first_nm_conn<'a>(
    nm_conns_name_type_index: &'a HashMap<
        (&'a str, &'a str),
        Vec<&'a NmConnection>,
    >,
    name: &'a str,
    nm_iface_type: &'a str,
) -> Option<&'a NmConnection> {
    // Treating veth as ethernet
    let nm_iface_type = if nm_iface_type == NM_SETTING_VETH_SETTING_NAME {
        NM_SETTING_WIRED_SETTING_NAME
    } else {
        nm_iface_type
    };
    if let Some(nm_conns) = nm_conns_name_type_index.get(&(name, nm_iface_type))
    {
        if nm_conns.is_empty() {
            None
        } else {
            Some(nm_conns[0])
        }
    } else {
        None
    }
}

fn get_nm_ac<'a>(
    nm_acs_name_type_index: &'a HashMap<
        (&'a str, &'a str),
        &'a NmActiveConnection,
    >,
    name: &'a str,
    nm_iface_type: &'a str,
) -> Option<&'a NmActiveConnection> {
    nm_acs_name_type_index.get(&(name, nm_iface_type)).copied()
}

fn set_ovs_iface_controller_info(ifaces: &mut Interfaces) {
    let mut pending_changes: Vec<(&str, &str)> = Vec::new();
    for iface in ifaces.user_ifaces.values() {
        if iface.iface_type() == InterfaceType::OvsBridge {
            if let Some(port_names) = iface.ports() {
                for port_name in port_names {
                    pending_changes.push((port_name, iface.name()));
                }
            }
        }
    }
    for (iface_name, ctrl_name) in pending_changes {
        if let Some(ref mut iface) = ifaces.kernel_ifaces.get_mut(iface_name) {
            iface.base_iface_mut().prop_list.push("controller");
            iface.base_iface_mut().prop_list.push("controller_type");
            iface.base_iface_mut().controller = Some(ctrl_name.to_string());
            iface.base_iface_mut().controller_type =
                Some(InterfaceType::OvsBridge);
        }
    }
}
