// SPDX-License-Identifier: Apache-2.0

use crate::{Interface, InterfaceType, Interfaces};

// Above this many related interfaces (not counting the interface itself),
// querying them one by one is not expected to be cheaper than querying
// everything.
const MAX_RELATED_IFACES: usize = 16;

/// Return the names of the kernel interfaces whose NetworkManager
/// information is needed to report `iface_name`: the interface itself, its
/// controller, its ports and the interfaces it is linked to (parent, veth
/// peer).
///
/// Return `None` when the full state has to be retrieved instead: the
/// interface is not a kernel interface, anything related is OVS, TUN or
/// unknown to the kernel, or there are more than `MAX_RELATED_IFACES` related
/// interfaces besides the interface itself.
pub(crate) fn get_related_iface_names(
    ifaces: &Interfaces,
    iface_name: &str,
) -> Option<Vec<String>> {
    let iface = ifaces.kernel_ifaces.get(iface_name)?;

    let mut names: Vec<String> = vec![iface_name.to_string()];
    let mut add = |name: &str| {
        if !name.is_empty() && !names.iter().any(|n| n == name) {
            names.push(name.to_string());
        }
    };

    if let Some(ctrl) = iface.base_iface().controller.as_deref() {
        add(ctrl);
    }
    for port in iface.ports().unwrap_or_default() {
        add(port);
    }
    for linked in linked_iface_names(iface) {
        add(linked);
    }
    for other in ifaces.kernel_ifaces.values() {
        if other.base_iface().controller.as_deref() == Some(iface_name) {
            add(other.name());
        }
    }

    if names.len() > MAX_RELATED_IFACES + 1 {
        log::debug!(
            "Interface {iface_name} has {} related interfaces, retrieving \
             full state",
            names.len()
        );
        return None;
    }

    for name in &names {
        match ifaces.kernel_ifaces.get(name) {
            Some(i) if !is_ovs_or_tun(i) => (),
            _ => {
                log::debug!(
                    "Interface {iface_name} is related to OVS, TUN or \
                     non-kernel interface {name}, retrieving full state"
                );
                return None;
            }
        }
    }
    Some(names)
}

// OVS interfaces combine data of several NetworkManager devices, and OVS
// netdev datapath uses TUN interfaces, which are only recognized as OVS when
// the OVS database is available. Leave them all on the full query.
fn is_ovs_or_tun(iface: &Interface) -> bool {
    matches!(
        iface.iface_type(),
        InterfaceType::OvsBridge
            | InterfaceType::OvsInterface
            | InterfaceType::Tun
    ) || iface.base_iface().controller_type == Some(InterfaceType::OvsBridge)
        || iface.base_iface().controller.as_deref() == Some("ovs-system")
}

// Names of interfaces this interface is linked to: parent and veth peer.
fn linked_iface_names(iface: &Interface) -> Vec<&str> {
    let mut ret = Vec::new();
    if let Some(parent) = iface.parent() {
        ret.push(parent);
    }
    match iface {
        Interface::Ethernet(eth) => {
            if let Some(veth) = eth.veth.as_ref() {
                ret.push(veth.peer.as_str());
            }
        }
        Interface::IpVlan(ipvlan) => {
            if let Some(base) =
                ipvlan.ipvlan.as_ref().and_then(|c| c.base_iface.as_deref())
            {
                ret.push(base);
            }
        }
        Interface::IpTunnel(tunnel) => {
            if let Some(base) = tunnel
                .ip_tunnel
                .as_ref()
                .and_then(|c| c.base_iface.as_deref())
            {
                ret.push(base);
            }
        }
        _ => (),
    }
    ret
}
