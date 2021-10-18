use log::{debug, warn};

use crate::{
    nispor::{
        base_iface::np_iface_to_base_iface, error::np_error_to_nmstate,
        ethernet::np_ethernet_to_nmstate, linux_bridge::np_bridge_to_nmstate,
        veth::np_veth_to_nmstate, vlan::np_vlan_to_nmstate,
    },
    DummyInterface, Interface, InterfaceType, NetworkState, NmstateError,
    UnknownInterface,
};

pub(crate) fn nispor_retrieve() -> Result<NetworkState, NmstateError> {
    let mut net_state = NetworkState::new();
    net_state.prop_list.push("interfaces");
    let mut np_state =
        nispor::NetState::retrieve().map_err(np_error_to_nmstate)?;

    for (_, np_iface) in np_state.ifaces.drain() {
        let mut base_iface = np_iface_to_base_iface(&np_iface);
        let iface = match &base_iface.iface_type {
            InterfaceType::LinuxBridge => Interface::LinuxBridge(
                np_bridge_to_nmstate(np_iface, base_iface),
            ),
            InterfaceType::Ethernet => Interface::Ethernet(
                np_ethernet_to_nmstate(np_iface, base_iface),
            ),
            InterfaceType::Veth => {
                base_iface.iface_type = InterfaceType::Ethernet;
                Interface::Ethernet(np_veth_to_nmstate(np_iface, base_iface))
            }
            InterfaceType::Vlan => {
                Interface::Vlan(np_vlan_to_nmstate(np_iface, base_iface))
            }
            InterfaceType::Loopback | InterfaceType::Tun => {
                // Nmstate has no plan on supporting loopback/tun interface
                continue;
            }
            InterfaceType::Dummy => {
                Interface::Dummy(DummyInterface::new(base_iface))
            }
            _ => {
                warn!(
                    "Got unsupported interface {} type {:?}",
                    np_iface.name, np_iface.iface_type
                );
                Interface::Unknown(UnknownInterface::new(base_iface))
            }
        };
        debug!("Got interface {:?}", iface);
        net_state.append_interface_data(iface);
    }
    Ok(net_state)
}
