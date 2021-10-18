use log::{debug, warn};
use nm_dbus::{
    NmApi, NmConnection, NmDeviceState, NmSettingIp, NmSettingIpMethod,
};

use crate::{
    nm::connection::create_index_for_nm_conns, nm::error::nm_error_to_nmstate,
    BaseInterface, EthernetInterface, Interface, InterfaceIpv4, InterfaceIpv6,
    InterfaceState, InterfaceType, LinuxBridgeInterface, NetworkState,
    NmstateError, UnknownInterface,
};

const NM_SETTING_BRIDGE_SETTING_NAME: &str = "bridge";
const NM_SETTING_WIRED_SETTING_NAME: &str = "802-3-ethernet";

pub(crate) fn nm_retrieve() -> Result<NetworkState, NmstateError> {
    let mut net_state = NetworkState::new();
    net_state.prop_list = vec!["interfaces"];
    let nm_api = NmApi::new().map_err(nm_error_to_nmstate)?;
    let nm_conns = nm_api
        .applied_connections_get()
        .map_err(nm_error_to_nmstate)?;
    let nm_devs = nm_api.devices_get().map_err(nm_error_to_nmstate)?;

    let nm_conn_indexed = create_index_for_nm_conns(nm_conns.as_slice());

    // Include disconnected interface as state:down
    // This is used for verify on `state: absent`
    for nm_dev in &nm_devs {
        match nm_dev.state {
            NmDeviceState::Unmanaged => continue,
            NmDeviceState::Disconnected => {
                let iface_type = nm_iface_type_to_nmstate(&nm_dev.iface_type);
                let base_iface = BaseInterface {
                    name: nm_dev.name.clone(),
                    prop_list: vec!["name", "iface_type", "state"],
                    state: InterfaceState::Down,
                    iface_type,
                    ..Default::default()
                };
                let iface = match &base_iface.iface_type {
                    InterfaceType::Ethernet => {
                        Interface::Ethernet(EthernetInterface {
                            base: base_iface,
                            ..Default::default()
                        })
                    }
                    InterfaceType::LinuxBridge => {
                        Interface::LinuxBridge(LinuxBridgeInterface {
                            base: base_iface,
                            ..Default::default()
                        })
                    }
                    _ => Interface::Unknown(UnknownInterface::new(base_iface)),
                };
                debug!("Found disconnected interface {:?}", iface);
                net_state.append_interface_data(iface);
            }
            _ => {
                if let Some(nm_conns) = nm_conn_indexed
                    .get(&(nm_dev.name.clone(), nm_dev.iface_type.clone()))
                {
                    // There is only single applied connection for each device
                    let nm_conn = if nm_conns.is_empty() {
                        continue;
                    } else {
                        nm_conns[0]
                    };

                    if let Some(base_iface) = nm_conn_to_base_iface(nm_conn) {
                        let iface = match &base_iface.iface_type {
                            InterfaceType::LinuxBridge => {
                                Interface::LinuxBridge(LinuxBridgeInterface {
                                    base: base_iface,
                                    ..Default::default()
                                })
                            }
                            InterfaceType::Ethernet => {
                                Interface::Ethernet(EthernetInterface {
                                    base: base_iface,
                                    ..Default::default()
                                })
                            }
                            _ => Interface::Unknown(UnknownInterface::new(
                                base_iface,
                            )),
                        };
                        debug!("Found interface {:?}", iface);
                        net_state.append_interface_data(iface);
                    }
                }
            }
        }
    }

    Ok(net_state)
}

fn nm_iface_type_to_nmstate(nm_iface_type: &str) -> InterfaceType {
    match nm_iface_type {
        NM_SETTING_WIRED_SETTING_NAME => InterfaceType::Ethernet,
        NM_SETTING_BRIDGE_SETTING_NAME => InterfaceType::LinuxBridge,
        _ => InterfaceType::Unknown,
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

            return Some(BaseInterface {
                name: iface_name.to_string(),
                prop_list: vec!["name", "state", "iface_type", "ipv4", "ipv6"],
                state: InterfaceState::Up,
                iface_type: nm_iface_type_to_nmstate(iface_type),
                ipv4,
                ipv6,
                ..Default::default()
            });
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
            | NmSettingIpMethod::Shared => (true, false, true),
            NmSettingIpMethod::Auto => (true, true, true),
            NmSettingIpMethod::Dhcp => (true, true, false),
            NmSettingIpMethod::Ignore => (true, false, true),
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
