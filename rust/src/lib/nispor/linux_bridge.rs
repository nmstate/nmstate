use crate::{
    BaseInterface, LinuxBridgeConfig, LinuxBridgeInterface, LinuxBridgeOptions,
    LinuxBridgePortConfig, LinuxBridgeStpOptions,
};

pub(crate) fn np_bridge_to_nmstate(
    np_iface: nispor::Iface,
    base_iface: BaseInterface,
) -> LinuxBridgeInterface {
    LinuxBridgeInterface {
        base: base_iface,
        bridge: Some(LinuxBridgeConfig {
            port: Some(np_bridge_ports_to_nmstate(&np_iface)),
            options: Some(np_bridge_options_to_nmstate(&np_iface)),
        }),
    }
}

fn np_bridge_ports_to_nmstate(
    np_iface: &nispor::Iface,
) -> Vec<LinuxBridgePortConfig> {
    let mut ports = Vec::new();
    if let Some(np_bridge) = &np_iface.bridge {
        for port_iface_name in &np_bridge.ports {
            ports.push(LinuxBridgePortConfig {
                name: port_iface_name.to_string(),
                ..Default::default()
            });
        }
    }
    ports
}

fn np_bridge_options_to_nmstate(
    np_iface: &nispor::Iface,
) -> LinuxBridgeOptions {
    let mut options = LinuxBridgeOptions::default();
    if let Some(ref np_bridge) = &np_iface.bridge {
        options.stp = Some(LinuxBridgeStpOptions {
            enabled: Some(
                [
                    Some(nispor::BridgeStpState::KernelStp),
                    Some(nispor::BridgeStpState::UserStp),
                ]
                .contains(&np_bridge.stp_state),
            ),
        });
    }
    options
}
