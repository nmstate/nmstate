use log::{debug, warn};

use crate::{
    nispor::{
        base_iface::np_iface_to_base_iface,
        bond::np_bond_to_nmstate,
        error::np_error_to_nmstate,
        ethernet::np_ethernet_to_nmstate,
        linux_bridge::{append_bridge_port_config, np_bridge_to_nmstate},
        route::get_routes,
        veth::np_veth_to_nmstate,
        vlan::np_vlan_to_nmstate,
    },
    DummyInterface, Interface, InterfaceType, NetworkState, NmstateError,
    OvsInterface, UnknownInterface,
};

pub(crate) fn nispor_retrieve() -> Result<NetworkState, NmstateError> {
    let mut net_state = NetworkState::new();
    net_state.prop_list.push("interfaces");
    net_state.prop_list.push("routes");
    let np_state = nispor::NetState::retrieve().map_err(np_error_to_nmstate)?;

    for (_, np_iface) in np_state.ifaces.iter() {
        let mut base_iface = np_iface_to_base_iface(np_iface);
        // The `ovs-system` is reserved for OVS kernel datapath
        if np_iface.name == "ovs-system" {
            continue;
        }

        let iface = match &base_iface.iface_type {
            InterfaceType::LinuxBridge => {
                let mut br_iface = np_bridge_to_nmstate(np_iface, base_iface);
                let mut port_np_ifaces = Vec::new();
                for port_name in br_iface.ports().unwrap_or_default() {
                    if let Some(p) = np_state.ifaces.get(port_name) {
                        port_np_ifaces.push(p)
                    }
                }
                append_bridge_port_config(
                    &mut br_iface,
                    np_iface,
                    port_np_ifaces,
                );
                Interface::LinuxBridge(br_iface)
            }
            InterfaceType::Bond => {
                Interface::Bond(np_bond_to_nmstate(np_iface, base_iface))
            }
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
            InterfaceType::Dummy => Interface::Dummy({
                let mut iface = DummyInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::OvsInterface => Interface::OvsInterface({
                let mut iface = OvsInterface::new();
                iface.base = base_iface;
                iface
            }),
            _ => {
                warn!(
                    "Got unsupported interface {} type {:?}",
                    np_iface.name, np_iface.iface_type
                );
                Interface::Unknown({
                    let mut iface = UnknownInterface::new();
                    iface.base = base_iface;
                    iface
                })
            }
        };
        debug!("Got interface {:?}", iface);
        net_state.append_interface_data(iface);
    }
    net_state.routes = get_routes(&np_state.routes);

    Ok(net_state)
}
