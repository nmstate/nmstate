// SPDX-License-Identifier: Apache-2.0

use crate::nm::nm_dbus::{
    NmActiveConnection, NmApi, NmConnection, NmDevice, NmDeviceState,
    NmIfaceType, NmLldpNeighbor,
};

use super::{
    error::nm_error_to_nmstate,
    query_apply::{
        device::nm_dev_iface_type_to_nmstate, dispatch::get_dispatches,
        dns::nm_global_dns_to_nmstate, get_description, get_lldp,
        is_lldp_enabled, nm_802_1x_to_nmstate, nm_ip_setting_to_nmstate4,
        nm_ip_setting_to_nmstate6, ovs::merge_ovs_netdev_tun_iface,
        query_nmstate_wait_ip, retrieve_dns_info,
        vpn::get_supported_vpn_ifaces,
    },
    settings::get_bond_balance_slb,
    NmConnectionMatcher,
};
use crate::{
    BaseInterface, BondConfig, BondInterface, BondOptions, DummyInterface,
    EthernetInterface, HsrInterface, InfiniBandInterface, Interface,
    InterfaceIdentifier, InterfaceState, InterfaceType, IpVlanInterface,
    LinuxBridgeInterface, LoopbackInterface, MacSecConfig, MacSecInterface,
    MacVlanInterface, MacVtapInterface, MergedNetworkState, NetworkState,
    NetworkStateMode, NmstateError, OvsBridgeInterface, OvsInterface,
    PciAddress, UnknownInterface, VlanInterface, VrfInterface, VxlanInterface,
};

/// The `current_state` is NetworkState retrieved by nispor, and will be used
/// for matching NmConnection to real network interface.
pub(crate) async fn nm_retrieve(
    running_config_only: bool,
    current_state: &NetworkState,
) -> Result<NetworkState, NmstateError> {
    let mut net_state = NetworkState::new();
    let mut nm_api = NmApi::new().await.map_err(nm_error_to_nmstate)?;
    let nm_applied_conns = nm_api
        .applied_connections_get()
        .await
        .map_err(nm_error_to_nmstate)?;

    let nm_saved_conns = nm_api
        .connections_get()
        .await
        .map_err(nm_error_to_nmstate)?;
    let nm_acs = nm_api
        .active_connections_get()
        .await
        .map_err(nm_error_to_nmstate)?;

    let conn_matcher = NmConnectionMatcher::new(
        nm_saved_conns,
        nm_applied_conns,
        nm_acs,
        &MergedNetworkState::new(
            NetworkState::default(),
            current_state.clone(),
            NetworkStateMode::default(),
            false,
        )?
        .interfaces,
    );

    let nm_devs = nm_api.devices_get().await.map_err(nm_error_to_nmstate)?;

    // Include disconnected interface as state:down
    // This is used for verify on `state: absent`
    for nm_dev in &nm_devs {
        // The OVS `netdev` datapath has both ovs-interface and
        // tun interface, we only store ovs-interface here, then
        // `merge_ovs_netdev_tun_iface()` afterwards
        if nm_dev.iface_type == NmIfaceType::Tun
            && nm_devs.as_slice().iter().any(|n| {
                n.name == nm_dev.name && n.iface_type == NmIfaceType::OvsIface
            })
        {
            continue;
        }
        if nm_dev.name.as_str() == "ip_vti0" {
            log::debug!("Skipping libreswan ip_vti0 interface");
            continue;
        }

        let mut iface = match nm_dev_to_nm_iface(nm_dev) {
            Some(i) => i,
            None => continue,
        };

        // We copy MAc address of interface from current_state to help
        // NmConnectionMatcher to find the correct one.
        if let Some(cur_iface) = current_state
            .interfaces
            .get_iface(iface.name(), iface.iface_type())
        {
            iface
                .base_iface_mut()
                .mac_address
                .clone_from(&cur_iface.base_iface().mac_address);
        }

        if iface.is_ignore() {
            net_state.append_interface_data(iface);
            continue;
        }

        let nm_ac = conn_matcher.get_nm_ac(iface.base_iface());

        if let Some(state_flag) = nm_ac.map(|nm_ac| nm_ac.state_flags) {
            if (state_flag & NmActiveConnection::STATE_FLAG_EXTERNAL) > 0 {
                log::debug!(
                    "Found external managed interface {}/{}",
                    iface.name(),
                    iface.iface_type()
                );
                net_state.append_interface_data(iface);
                continue;
            }
        }

        let nm_saved_conn = conn_matcher.get_prefered_saved(iface.base_iface());
        let nm_applied_conn = if let Some(nm_ac) = nm_ac.as_ref() {
            conn_matcher
                .get_applied_by_uuid(nm_ac.uuid.as_str())
                .or_else(|| conn_matcher.get_applied(iface.base_iface()))
        } else {
            conn_matcher.get_applied(iface.base_iface())
        };

        let lldp_neighbors =
            if let Some(nm_applied_conn) = nm_applied_conn.as_ref() {
                if is_lldp_enabled(nm_applied_conn) {
                    if running_config_only {
                        Some(Vec::new())
                    } else {
                        Some(
                            nm_api
                                .device_lldp_neighbor_get(&nm_dev.obj_path)
                                .await
                                .map_err(nm_error_to_nmstate)?,
                        )
                    }
                } else {
                    None
                }
            } else {
                None
            };

        fill_iface_by_nm_conn_data(
            &mut iface,
            nm_applied_conn,
            nm_saved_conn,
            lldp_neighbors,
        );

        net_state.append_interface_data(iface);
    }

    for iface in get_supported_vpn_ifaces(&conn_matcher)? {
        net_state.append_interface_data(iface);
    }

    for iface in net_state
        .interfaces
        .kernel_ifaces
        .values_mut()
        .chain(net_state.interfaces.user_ifaces.values_mut())
    {
        // Do not touch interfaces nmstate does not support yet
        if !InterfaceType::SUPPORTED_LIST.contains(&iface.iface_type()) {
            iface.base_iface_mut().state = InterfaceState::Ignore;
        }
    }

    let mut dns_config = if let Ok(nm_global_dns_conf) = nm_api
        .get_global_dns_configuration()
        .await
        .map_err(nm_error_to_nmstate)
    {
        if nm_global_dns_conf.is_empty() {
            retrieve_dns_info(&mut nm_api, &net_state.interfaces).await?
        } else {
            nm_global_dns_to_nmstate(&nm_global_dns_conf)
        }
    } else {
        retrieve_dns_info(&mut nm_api, &net_state.interfaces).await?
    };
    dns_config.sanitize().ok();
    if running_config_only {
        dns_config.running = None;
    }
    net_state.dns = Some(dns_config);

    for (iface_name, conf) in get_dispatches().drain() {
        if let Some(iface) =
            net_state.interfaces.kernel_ifaces.get_mut(&iface_name)
        {
            iface.base_iface_mut().dispatch = Some(conf);
        }
    }

    merge_ovs_netdev_tun_iface(&mut net_state, &conn_matcher);

    Ok(net_state)
}

fn fill_ip_settings(base_iface: &mut BaseInterface, nm_conn: &NmConnection) {
    base_iface.ipv4 = nm_conn.ipv4.as_ref().map(nm_ip_setting_to_nmstate4);
    base_iface.ipv6 = nm_conn.ipv6.as_ref().map(|nm_ip_set| {
        nm_ip_setting_to_nmstate6(base_iface.name.as_str(), nm_ip_set)
    });
    base_iface.wait_ip =
        query_nmstate_wait_ip(nm_conn.ipv4.as_ref(), nm_conn.ipv6.as_ref());
}

// Applied connection does not hold OVS config, we need the saved NmConnection
// used by `NmActiveConnection` in this case.
pub(crate) fn fill_iface_by_nm_conn_data(
    iface: &mut Interface,
    nm_applied_conn: Option<&NmConnection>,
    nm_saved_conn: Option<&NmConnection>,
    lldp_neighbors: Option<Vec<NmLldpNeighbor>>,
) {
    let base_iface = iface.base_iface_mut();

    // Fallback to saved NmConnection when applied is empty
    if let Some(nm_conn) = nm_applied_conn.or(nm_saved_conn) {
        fill_ip_settings(base_iface, nm_conn);
        base_iface.description = get_description(nm_conn);
        fill_identifier(base_iface, nm_conn);
        base_iface.profile_name = get_connection_name(nm_conn, nm_saved_conn);
        if base_iface.profile_name.as_ref() == Some(&base_iface.name) {
            base_iface.profile_name = None;
        }
        base_iface.lldp =
            Some(lldp_neighbors.map(get_lldp).unwrap_or_default());
    }

    if let Some(nm_saved_conn) = nm_saved_conn {
        // 802.1x password is only available in saved connection
        base_iface.ieee8021x =
            nm_saved_conn.ieee8021x.as_ref().map(nm_802_1x_to_nmstate);
    }

    if let Interface::Bond(bond_iface) = iface {
        let bond_config = BondConfig {
            options: Some(BondOptions {
                balance_slb: nm_applied_conn.and_then(get_bond_balance_slb),
                ..Default::default()
            }),
            ..Default::default()
        };
        bond_iface.bond = Some(bond_config);
    } else if let Interface::MacSec(mac_sec_iface) = iface {
        if let Some(macsec_set) =
            nm_applied_conn.and_then(|n| n.macsec.as_ref())
        {
            let mut macsec_config = MacSecConfig::new();
            macsec_config.mka_ckn.clone_from(&macsec_set.mka_ckn);
            // The `mka_cak` is stored in saved NmConnection only
            if let Some(saved_conn) = nm_saved_conn.as_ref() {
                if let Some(macsec_saved_set) = saved_conn.macsec.as_ref() {
                    macsec_config.mka_cak.clone_from(&macsec_saved_set.mka_cak);
                }
            }
            mac_sec_iface.macsec = Some(macsec_config);
        }
    }
}

fn nm_dev_to_nm_iface(nm_dev: &NmDevice) -> Option<Interface> {
    let mut base_iface = BaseInterface::new();
    if nm_dev.name.is_empty() {
        return None;
    } else {
        base_iface.name.clone_from(&nm_dev.name);
    }
    match nm_dev.state {
        NmDeviceState::Unmanaged => {
            if !nm_dev.real {
                return None;
            } else {
                base_iface.state = InterfaceState::Ignore;
            }
        }
        NmDeviceState::Disconnected => base_iface.state = InterfaceState::Down,
        _ => base_iface.state = InterfaceState::Up,
    }
    base_iface.iface_type = nm_dev_iface_type_to_nmstate(nm_dev);
    let iface = match &base_iface.iface_type {
        InterfaceType::Ethernet => Interface::Ethernet({
            let mut iface = EthernetInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::Dummy => Interface::Dummy({
            let mut iface = DummyInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::LinuxBridge => Interface::LinuxBridge({
            let mut iface = LinuxBridgeInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::OvsInterface => Interface::OvsInterface({
            let mut iface = OvsInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::OvsBridge => Interface::OvsBridge({
            let mut iface = OvsBridgeInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::Bond => Interface::Bond({
            let mut iface = BondInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::Vlan => Interface::Vlan({
            let mut iface = VlanInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::Vxlan => Interface::Vxlan({
            let mut iface = VxlanInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::MacVlan => Interface::MacVlan({
            let mut iface = MacVlanInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::MacVtap => Interface::MacVtap({
            let mut iface = MacVtapInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::Vrf => Interface::Vrf({
            let mut iface = VrfInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::Loopback => Interface::Loopback({
            let mut iface = LoopbackInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::MacSec => Interface::MacSec({
            let mut iface = MacSecInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::Hsr => Interface::Hsr({
            let mut iface = HsrInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        InterfaceType::InfiniBand => Interface::InfiniBand(Box::new({
            InfiniBandInterface {
                base: base_iface,
                ..Default::default()
            }
        })),
        InterfaceType::IpVlan => Interface::IpVlan({
            let mut iface = IpVlanInterface::new();
            iface.base = base_iface;
            Box::new(iface)
        }),
        iface_type
            if iface_type == &InterfaceType::Other("ovs-port".to_string()) =>
        {
            log::debug!(
                "Skipping unmanaged/disconnected NM speicifc OVS-port {}",
                base_iface.name
            );
            return None;
        }
        iface_type => {
            log::info!(
                "Got unsupported interface type {}: {}, ignoring",
                iface_type,
                base_iface.name
            );
            // On NM 1.42- , the loopback is holding "generic" nm interface
            // type.
            base_iface.state = InterfaceState::Ignore;
            if base_iface.name == "lo" {
                let mut iface = LoopbackInterface::new();
                base_iface.iface_type = InterfaceType::Loopback;
                iface.base = base_iface;
                Interface::Loopback(Box::new(iface))
            } else {
                // For unknown/unsupported interface,
                // if it has MAC address, we treat it as UnknownInterface which
                // is a kernel interface, otherwise use OtherInterface which is
                // a user space interface.
                if !nm_dev.mac_address.is_empty() {
                    base_iface.iface_type = InterfaceType::Unknown;
                }
                let mut iface = UnknownInterface::new();
                iface.base = base_iface;
                Interface::Unknown(Box::new(iface))
            }
        }
    };
    Some(iface)
}

// If identifier is mac-address, we should override MAC address
// queried by nispor, otherwise applying back the queried state will
// be different for bond ports as their MAC address will change after
// attached to bond.
// For InterfaceIdentifier::Name, we set mac and pci address to None.
// For InterfaceIdentifier::PciAddress, we override pci address queried by
// nispor.
// TODO: Once we have dedicate section for `identifier`, we should
//       not override runtime MAC address.
fn fill_identifier(base_iface: &mut BaseInterface, nm_conn: &NmConnection) {
    base_iface.identifier = Some(InterfaceIdentifier::Name);
    base_iface.mac_address = None;
    base_iface.pci_address = None;

    if let Some(nm_set) = nm_conn.wired.as_ref() {
        if let Some(mac) = nm_set.mac_address.as_deref() {
            if !mac.is_empty() {
                base_iface.identifier = Some(InterfaceIdentifier::MacAddress);
                base_iface.mac_address = Some(mac.to_string());
            }
        }
    }

    if let Some(pci_addr_str) = nm_conn
        .iface_match
        .as_ref()
        .and_then(|s| s.path.as_ref())
        .and_then(|p| p.first())
        .and_then(|p| p.strip_prefix("pci-"))
    {
        if let Ok(pci_addr) = PciAddress::try_from(pci_addr_str) {
            base_iface.identifier = Some(InterfaceIdentifier::PciAddress);
            base_iface.pci_address = Some(pci_addr);
        }
    }
}

// The applied connection will not update `connection.id` when reapply due to
// bug: https://issues.redhat.com/browse/RHEL-59548
// Hence we prefer saved NmConnection over active when they are pointing to the
// same UUID.
fn get_connection_name(
    nm_conn: &NmConnection,
    saved_nm_conn: Option<&NmConnection>,
) -> Option<String> {
    if let Some(saved_nm_conn) = saved_nm_conn.as_ref() {
        if saved_nm_conn.uuid() == nm_conn.uuid() {
            if let Some(nm_set) = saved_nm_conn.connection.as_ref() {
                return nm_set.id.clone();
            }
        }
    }
    if let Some(nm_set) = nm_conn.connection.as_ref() {
        return nm_set.id.clone();
    }
    None
}
