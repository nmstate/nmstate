use log::warn;

use crate::{
    nispor::{
        ip::{nmstate_ipv4_to_np, nmstate_ipv6_to_np},
        veth::nms_veth_conf_to_np,
        vlan::nms_vlan_conf_to_np,
    },
    ErrorKind, Interface, InterfaceType, NetworkState, NmstateError,
};

pub(crate) fn nispor_apply(
    add_net_state: &NetworkState,
    chg_net_state: &NetworkState,
    del_net_state: &NetworkState,
    _full_net_state: &NetworkState,
) -> Result<(), NmstateError> {
    apply_single_state(del_net_state)?;
    apply_single_state(add_net_state)?;
    apply_single_state(chg_net_state)?;
    Ok(())
}

fn net_state_to_nispor(
    net_state: &NetworkState,
) -> Result<nispor::NetConf, NmstateError> {
    let mut np_ifaces: Vec<nispor::IfaceConf> = Vec::new();

    for iface in net_state.interfaces.to_vec() {
        if iface.is_up() {
            let np_iface_type = nmstate_iface_type_to_np(&iface.iface_type());
            if np_iface_type == nispor::IfaceType::Unknown {
                warn!(
                    "Unknown interface type {} for interface {}",
                    iface.iface_type(),
                    iface.name()
                );
                continue;
            }
            np_ifaces.push(nmstate_iface_to_np(iface, np_iface_type)?);
        } else if iface.is_absent() {
            np_ifaces.push(nispor::IfaceConf {
                name: iface.name().to_string(),
                iface_type: Some(nmstate_iface_type_to_np(&iface.iface_type())),
                state: nispor::IfaceState::Absent,
                ..Default::default()
            });
        }
    }

    Ok(nispor::NetConf {
        ifaces: Some(np_ifaces),
    })
}

fn nmstate_iface_type_to_np(
    nms_iface_type: &InterfaceType,
) -> nispor::IfaceType {
    match nms_iface_type {
        InterfaceType::LinuxBridge => nispor::IfaceType::Bridge,
        InterfaceType::Ethernet => nispor::IfaceType::Ethernet,
        InterfaceType::Veth => nispor::IfaceType::Veth,
        InterfaceType::Vlan => nispor::IfaceType::Vlan,
        _ => nispor::IfaceType::Unknown,
    }
}

fn nmstate_iface_to_np(
    nms_iface: &Interface,
    np_iface_type: nispor::IfaceType,
) -> Result<nispor::IfaceConf, NmstateError> {
    let mut np_iface = nispor::IfaceConf {
        name: nms_iface.name().to_string(),
        iface_type: Some(np_iface_type),
        state: nispor::IfaceState::Up,
        ..Default::default()
    };
    let base_iface = &nms_iface.base_iface();
    if let Some(ctrl_name) = &base_iface.controller {
        np_iface.controller = Some(ctrl_name.to_string())
    }
    if base_iface.can_have_ip() {
        np_iface.ipv4 = Some(nmstate_ipv4_to_np(base_iface.ipv4.as_ref()));
        np_iface.ipv6 = Some(nmstate_ipv6_to_np(base_iface.ipv6.as_ref()));
    }

    np_iface.mac_address = base_iface.mac_address.clone();

    if let Interface::Ethernet(eth_iface) = nms_iface {
        np_iface.veth = nms_veth_conf_to_np(eth_iface.veth.as_ref());
    } else if let Interface::Vlan(vlan_iface) = nms_iface {
        np_iface.vlan = nms_vlan_conf_to_np(vlan_iface.vlan.as_ref());
    }

    Ok(np_iface)
}

fn apply_single_state(net_state: &NetworkState) -> Result<(), NmstateError> {
    let np_net_conf = net_state_to_nispor(net_state)?;
    if let Err(e) = np_net_conf.apply() {
        return Err(NmstateError::new(
            ErrorKind::PluginFailure,
            format!("Unknown error from nipsor plugin: {}, {}", e.kind, e.msg),
        ));
    } else {
        Ok(())
    }
}
