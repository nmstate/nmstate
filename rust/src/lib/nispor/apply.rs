// SPDX-License-Identifier: Apache-2.0

use crate::{
    nispor::{
        dns::apply_dns_conf_to_etc,
        hostname::set_running_hostname,
        ip::{nmstate_ipv4_to_np, nmstate_ipv6_to_np},
        route::gen_nispor_route_confs,
        veth::nms_veth_conf_to_np,
        vlan::nms_vlan_conf_to_np,
    },
    ErrorKind, Interface, InterfaceType, MergedInterface, MergedInterfaces,
    MergedNetworkState, NmstateError,
};

pub(crate) async fn nispor_apply(
    merged_state: &MergedNetworkState,
) -> Result<(), NmstateError> {
    delete_ifaces(&merged_state.interfaces).await?;

    let mut ifaces: Vec<&MergedInterface> = merged_state
        .interfaces
        .iter()
        .filter(|i| i.is_changed())
        .collect();

    ifaces.sort_unstable_by_key(|iface| iface.merged.name());
    // Use sort_by_key() instead of unstable one, do we can alphabet
    // activation order which is required to simulate the OS boot-up.
    ifaces.sort_by_key(|iface| {
        if let Some(i) = iface.for_apply.as_ref() {
            i.base_iface().up_priority
        } else {
            u32::MAX
        }
    });

    let mut np_ifaces: Vec<nispor::IfaceConf> = Vec::new();
    for merged_iface in ifaces.iter().filter(|i| {
        i.merged.iface_type() != InterfaceType::Unknown && !i.merged.is_absent()
    }) {
        if let Some(iface) = merged_iface.for_apply.as_ref() {
            np_ifaces.push(nmstate_iface_to_np(iface)?);
        }
    }

    let mut net_conf = nispor::NetConf::default();
    net_conf.ifaces = Some(np_ifaces);

    if merged_state.routes.is_changed() {
        net_conf.routes = Some(gen_nispor_route_confs(&merged_state.routes)?);
    }

    if let Err(e) = net_conf.apply_async().await {
        return Err(NmstateError::new(
            ErrorKind::PluginFailure,
            format!("Unknown error from nipsor plugin: {}, {}", e.kind, e.msg),
        ));
    }

    if let Some(running_hostname) = merged_state
        .hostname
        .desired
        .as_ref()
        .and_then(|c| c.running.as_ref())
    {
        set_running_hostname(running_hostname)?;
    }

    if merged_state.dns.is_changed() {
        apply_dns_conf_to_etc(&merged_state.dns)?;
    }

    Ok(())
}

fn nmstate_iface_type_to_np(
    nms_iface_type: &InterfaceType,
) -> nispor::IfaceType {
    match nms_iface_type {
        InterfaceType::LinuxBridge => nispor::IfaceType::Bridge,
        InterfaceType::Bond => nispor::IfaceType::Bond,
        InterfaceType::Ethernet => nispor::IfaceType::Ethernet,
        InterfaceType::Veth => nispor::IfaceType::Veth,
        InterfaceType::Vlan => nispor::IfaceType::Vlan,
        _ => nispor::IfaceType::Unknown,
    }
}

fn nmstate_iface_to_np(
    nms_iface: &Interface,
) -> Result<nispor::IfaceConf, NmstateError> {
    let mut np_iface = nispor::IfaceConf::default();

    let mut np_iface_type = nmstate_iface_type_to_np(&nms_iface.iface_type());

    if let Interface::Ethernet(iface) = nms_iface {
        if iface.veth.is_some() {
            np_iface_type = nispor::IfaceType::Veth;
        }
    }

    np_iface.name = nms_iface.name().to_string();
    np_iface.iface_type = Some(np_iface_type);
    if nms_iface.is_absent() {
        np_iface.state = nispor::IfaceState::Absent;
        return Ok(np_iface);
    }

    np_iface.state = nispor::IfaceState::Up;

    let base_iface = &nms_iface.base_iface();
    if let Some(ctrl_name) = &base_iface.controller {
        np_iface.controller = Some(ctrl_name.to_string())
    }
    if base_iface.can_have_ip() {
        np_iface.ipv4 = Some(nmstate_ipv4_to_np(base_iface.ipv4.as_ref()));
        np_iface.ipv6 = Some(nmstate_ipv6_to_np(base_iface.ipv6.as_ref()));
    }

    np_iface.mac_address.clone_from(&base_iface.mac_address);

    if let Interface::Ethernet(eth_iface) = nms_iface {
        np_iface.veth = nms_veth_conf_to_np(eth_iface.veth.as_ref());
    } else if let Interface::Vlan(vlan_iface) = nms_iface {
        np_iface.vlan = nms_vlan_conf_to_np(vlan_iface.vlan.as_ref());
    }

    Ok(np_iface)
}

async fn delete_ifaces(
    merged_ifaces: &MergedInterfaces,
) -> Result<(), NmstateError> {
    let mut deleted_veths: Vec<&str> = Vec::new();
    let mut np_ifaces: Vec<nispor::IfaceConf> = Vec::new();
    for iface in merged_ifaces
        .kernel_ifaces
        .values()
        .filter(|i| i.merged.is_absent())
    {
        // Deleting one end of veth peer is enough
        if deleted_veths.contains(&iface.merged.name()) {
            continue;
        }

        if let Some(Interface::Ethernet(eth_iface)) = &iface.current {
            if let Some(peer_name) = eth_iface
                .veth
                .as_ref()
                .map(|veth_conf| veth_conf.peer.as_str())
            {
                deleted_veths.push(eth_iface.base.name.as_str());
                deleted_veths.push(peer_name);
            }
        }
        if let Some(apply_iface) = iface.for_apply.as_ref() {
            np_ifaces.push(nmstate_iface_to_np(apply_iface)?);
        }
    }

    let mut net_conf = nispor::NetConf::default();
    net_conf.ifaces = Some(np_ifaces);

    if let Err(e) = net_conf.apply_async().await {
        Err(NmstateError::new(
            ErrorKind::PluginFailure,
            format!("Unknown error from nipsor plugin: {}, {}", e.kind, e.msg),
        ))
    } else {
        Ok(())
    }
}
