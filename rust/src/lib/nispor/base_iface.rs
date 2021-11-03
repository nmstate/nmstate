use crate::{
    nispor::ip::{np_ipv4_to_nmstate, np_ipv6_to_nmstate},
    BaseInterface, InterfaceState, InterfaceType,
};

fn np_iface_type_to_nmstate(
    np_iface_type: &nispor::IfaceType,
) -> InterfaceType {
    match np_iface_type {
        nispor::IfaceType::Bond => InterfaceType::Bond,
        nispor::IfaceType::Bridge => InterfaceType::LinuxBridge,
        nispor::IfaceType::Dummy => InterfaceType::Dummy,
        nispor::IfaceType::Ethernet => InterfaceType::Ethernet,
        nispor::IfaceType::Loopback => InterfaceType::Loopback,
        nispor::IfaceType::MacVlan => InterfaceType::MacVlan,
        nispor::IfaceType::MacVtap => InterfaceType::MacVtap,
        nispor::IfaceType::OpenvSwitch => InterfaceType::OvsInterface,
        nispor::IfaceType::Tun => InterfaceType::Tun,
        nispor::IfaceType::Veth => InterfaceType::Veth,
        nispor::IfaceType::Vlan => InterfaceType::Vlan,
        nispor::IfaceType::Vrf => InterfaceType::Vrf,
        nispor::IfaceType::Vxlan => InterfaceType::Vxlan,
        _ => InterfaceType::Other(format!("{:?}", np_iface_type)),
    }
}

fn np_iface_state_to_nmstate(
    np_iface_state: &nispor::IfaceState,
) -> InterfaceState {
    match np_iface_state {
        nispor::IfaceState::Up => InterfaceState::Up,
        nispor::IfaceState::Down => InterfaceState::Down,
        _ => InterfaceState::Unknown,
    }
}

pub(crate) fn np_iface_to_base_iface(
    np_iface: &nispor::Iface,
) -> BaseInterface {
    let base_iface = BaseInterface {
        name: np_iface.name.to_string(),
        state: np_iface_state_to_nmstate(&np_iface.state),
        iface_type: np_iface_type_to_nmstate(&np_iface.iface_type),
        ipv4: np_ipv4_to_nmstate(np_iface),
        ipv6: np_ipv6_to_nmstate(np_iface),
        mac_address: Some(np_iface.mac_address.to_uppercase()),
        controller: np_iface.controller.as_ref().map(|c| c.to_string()),
        mtu: if np_iface.mtu >= 0 {
            Some(np_iface.mtu as u64)
        } else {
            Some(0u64)
        },
        prop_list: vec![
            "name",
            "state",
            "iface_type",
            "ipv4",
            "ipv6",
            "mac_address",
            "controller",
            "mtu",
        ],
        ..Default::default()
    };
    base_iface
}
