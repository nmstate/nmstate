// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::nm::nm_dbus::{
    NmActiveConnection, NmApi, NmConnection, NmDevice, NmDeviceState,
    NmLldpNeighbor, NM_ACTIVATION_STATE_FLAG_EXTERNAL,
};

use super::{
    active_connection::create_index_for_nm_acs_by_name_type,
    error::nm_error_to_nmstate,
    query_apply::{
        create_index_for_nm_conns_by_name_type,
        device::nm_dev_iface_type_to_nmstate, dispatch::get_dispatches,
        dns::nm_global_dns_to_nmstate, get_description, get_lldp,
        is_lldp_enabled, nm_802_1x_to_nmstate, nm_ip_setting_to_nmstate4,
        nm_ip_setting_to_nmstate6, ovs::merge_ovs_netdev_tun_iface,
        query_nmstate_wait_ip, retrieve_dns_info,
        vpn::get_supported_vpn_ifaces,
    },
    settings::{
        get_bond_balance_slb, NM_SETTING_OVS_IFACE_SETTING_NAME,
        NM_SETTING_VETH_SETTING_NAME, NM_SETTING_WIRED_SETTING_NAME,
    },
};
use crate::{
    BaseInterface, BondConfig, BondInterface, BondOptions, DummyInterface,
    EthernetInterface, HsrInterface, InfiniBandInterface, Interface,
    InterfaceIdentifier, InterfaceState, InterfaceType, LinuxBridgeInterface,
    LoopbackInterface, MacSecConfig, MacSecInterface, MacVlanInterface,
    MacVtapInterface, NetworkState, NmstateError, OvsBridgeInterface,
    OvsInterface, UnknownInterface, VlanInterface, VrfInterface,
    VxlanInterface,
};

pub(crate) fn nm_retrieve(
    running_config_only: bool,
) -> Result<NetworkState, NmstateError> {
    let mut net_state = NetworkState::new();
    let mut nm_api = NmApi::new().map_err(nm_error_to_nmstate)?;
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
    let nm_acs_name_type_index =
        create_index_for_nm_acs_by_name_type(nm_acs.as_slice());

    // Include disconnected interface as state:down
    // This is used for verify on `state: absent`
    for nm_dev in &nm_devs {
        // The OVS `netdev` datapath has both ovs-interface and
        // tun interface, we only store ovs-interface here, then
        // `merge_ovs_netdev_tun_iface()` afterwards
        if nm_dev.iface_type == "tun"
            && nm_devs.as_slice().iter().any(|n| {
                n.name == nm_dev.name
                    && n.iface_type == NM_SETTING_OVS_IFACE_SETTING_NAME
            })
        {
            continue;
        }
        if nm_dev.name.as_str() == "ip_vti0" {
            log::debug!("Skipping libreswan ip_vti0 interface");
            continue;
        }
        match nm_dev.state {
            NmDeviceState::Unmanaged | NmDeviceState::Disconnected => {
                if let Some(iface) = nm_dev_to_nm_iface(nm_dev) {
                    log::debug!(
                        "Found unmanaged or disconnected interface {}/{}",
                        iface.name(),
                        iface.iface_type()
                    );
                    net_state.append_interface_data(iface);
                }
            }
            _ => {
                let nm_ac = get_nm_ac(
                    &nm_acs_name_type_index,
                    &nm_dev.name,
                    &nm_dev.iface_type,
                );
                if let Some(state_flag) = nm_ac.map(|nm_ac| nm_ac.state_flags) {
                    if (state_flag & NM_ACTIVATION_STATE_FLAG_EXTERNAL) > 0 {
                        if let Some(iface) = nm_dev_to_nm_iface(nm_dev) {
                            log::debug!(
                                "Found external managed interface {}/{}",
                                iface.name(),
                                iface.iface_type()
                            );
                            net_state.append_interface_data(iface);
                        }
                        continue;
                    }
                }

                let nm_conn = if let Some(c) = get_first_nm_conn(
                    &nm_conns_name_type_index,
                    &nm_dev.name,
                    &nm_dev.iface_type,
                ) {
                    c
                } else {
                    if nm_dev.state == NmDeviceState::Activated {
                        log::warn!(
                            "Failed to find applied NmConnection for \
                            interface {} {}",
                            nm_dev.name,
                            nm_dev.iface_type
                        );
                    }
                    continue;
                };

                // NM developer confirmed NmActiveConnection UUID is the
                // UUID of NmConnection associated
                let nm_saved_conn = if let Some(nm_ac) = nm_ac {
                    nm_saved_conn_uuid_index.get(nm_ac.uuid.as_str()).copied()
                } else {
                    None
                };

                let lldp_neighbors = if is_lldp_enabled(nm_conn) {
                    if running_config_only {
                        Some(Vec::new())
                    } else {
                        Some(
                            nm_api
                                .device_lldp_neighbor_get(&nm_dev.obj_path)
                                .map_err(nm_error_to_nmstate)?,
                        )
                    }
                } else {
                    None
                };
                if let Some(iface) =
                    iface_get(nm_dev, nm_conn, nm_saved_conn, lldp_neighbors)
                {
                    log::debug!(
                        "Found NM interface {}/{}",
                        iface.name(),
                        iface.iface_type()
                    );
                    net_state.append_interface_data(iface);
                }
            }
        }
    }
    for iface in get_supported_vpn_ifaces(&nm_saved_conn_uuid_index, &nm_acs)? {
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
        .map_err(nm_error_to_nmstate)
    {
        if nm_global_dns_conf.is_empty() {
            retrieve_dns_info(&mut nm_api, &net_state.interfaces)?
        } else {
            nm_global_dns_to_nmstate(&nm_global_dns_conf)
        }
    } else {
        retrieve_dns_info(&mut nm_api, &net_state.interfaces)?
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

    merge_ovs_netdev_tun_iface(&mut net_state, &nm_devs, &nm_conns);

    Ok(net_state)
}

// When nm_dev is None, this function will not set interface type.
pub(crate) fn nm_conn_to_base_iface(
    nm_dev: Option<&NmDevice>,
    nm_conn: &NmConnection,
    nm_saved_conn: Option<&NmConnection>,
    lldp_neighbors: Option<Vec<NmLldpNeighbor>>,
) -> Option<BaseInterface> {
    if let Some(iface_name) = nm_conn.iface_name().or_else(|| {
        if nm_conn.iface_type() == Some("vpn") {
            nm_conn.id()
        } else {
            None
        }
    }) {
        let ipv4 = nm_conn.ipv4.as_ref().map(nm_ip_setting_to_nmstate4);
        let ipv6 = nm_conn
            .ipv6
            .as_ref()
            .map(|nm_ip_set| nm_ip_setting_to_nmstate6(iface_name, nm_ip_set));

        let mut base_iface = BaseInterface::new();
        base_iface.name = iface_name.to_string();
        base_iface.state = InterfaceState::Up;
        base_iface.iface_type = if let Some(nm_dev) = nm_dev {
            nm_dev_iface_type_to_nmstate(nm_dev)
        } else {
            InterfaceType::Unknown
        };
        base_iface.ipv4 = ipv4;
        base_iface.ipv6 = ipv6;
        base_iface.wait_ip =
            query_nmstate_wait_ip(nm_conn.ipv4.as_ref(), nm_conn.ipv6.as_ref());
        base_iface.description = get_description(nm_conn);
        base_iface.identifier = Some(get_identifier(nm_conn));
        base_iface.profile_name = get_connection_name(nm_conn);
        if base_iface.profile_name.as_ref() == Some(&base_iface.name) {
            base_iface.profile_name = None;
        }

        base_iface.lldp =
            Some(lldp_neighbors.map(get_lldp).unwrap_or_default());
        if let Some(nm_saved_conn) = nm_saved_conn {
            // 802.1x password is only available in saved connection
            base_iface.ieee8021x =
                nm_saved_conn.ieee8021x.as_ref().map(nm_802_1x_to_nmstate);
        }
        return Some(base_iface);
    }
    None
}

// Applied connection does not hold OVS config, we need the NmConnection
// used by `NmActiveConnection` also.
fn iface_get(
    nm_dev: &NmDevice,
    nm_conn: &NmConnection,
    nm_saved_conn: Option<&NmConnection>,
    lldp_neighbors: Option<Vec<NmLldpNeighbor>>,
) -> Option<Interface> {
    if let Some(base_iface) = nm_conn_to_base_iface(
        Some(nm_dev),
        nm_conn,
        nm_saved_conn,
        lldp_neighbors,
    ) {
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
            InterfaceType::Bond => Interface::Bond({
                let mut iface = BondInterface::new();
                iface.base = base_iface;
                let bond_config = BondConfig {
                    options: Some(BondOptions {
                        balance_slb: get_bond_balance_slb(nm_conn),
                        ..Default::default()
                    }),
                    ..Default::default()
                };
                iface.bond = Some(bond_config);
                iface
            }),
            InterfaceType::OvsInterface => Interface::OvsInterface({
                let mut iface = OvsInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::Dummy => Interface::Dummy({
                let mut iface = DummyInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::Vlan => Interface::Vlan({
                let mut iface = VlanInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::Vxlan => Interface::Vxlan({
                let mut iface = VxlanInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::MacVlan => Interface::MacVlan({
                let mut iface = MacVlanInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::MacVtap => Interface::MacVtap({
                let mut iface = MacVtapInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::Vrf => Interface::Vrf({
                let mut iface = VrfInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::OvsBridge => Interface::OvsBridge({
                let mut iface = OvsBridgeInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::Loopback => Interface::Loopback({
                let mut iface = LoopbackInterface::new();
                iface.base = base_iface;
                iface
            }),
            InterfaceType::MacSec => Interface::MacSec({
                let mut iface = MacSecInterface::new();
                iface.base = base_iface;

                if let Some(macsec_set) = nm_conn.macsec.as_ref() {
                    let mut macsec_config = MacSecConfig::new();
                    macsec_config.mka_ckn = macsec_set.mka_ckn.clone();
                    if let Some(saved_conn) = nm_saved_conn.as_ref() {
                        if let Some(macsec_saved_set) =
                            saved_conn.macsec.as_ref()
                        {
                            macsec_config.mka_cak =
                                macsec_saved_set.mka_cak.clone();
                        }
                    }
                    iface.macsec = Some(macsec_config);
                }
                iface
            }),
            InterfaceType::Hsr => Interface::Hsr({
                let mut iface = HsrInterface::new();
                iface.base = base_iface;
                iface
            }),
            _ => {
                log::debug!("Skip unsupported interface {:?}", base_iface);
                return None;
            }
        };
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
    nm_acs_name_type_index
        .get(&(
            name,
            match nm_iface_type {
                NM_SETTING_VETH_SETTING_NAME => NM_SETTING_WIRED_SETTING_NAME,
                t => t,
            },
        ))
        .copied()
}

fn nm_dev_to_nm_iface(nm_dev: &NmDevice) -> Option<Interface> {
    let mut base_iface = BaseInterface::new();
    if nm_dev.name.is_empty() {
        return None;
    } else {
        base_iface.name = nm_dev.name.clone();
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
            iface
        }),
        InterfaceType::Dummy => Interface::Dummy({
            let mut iface = DummyInterface::new();
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
        InterfaceType::OvsBridge => Interface::OvsBridge({
            let mut iface = OvsBridgeInterface::new();
            iface.base = base_iface;
            iface
        }),
        InterfaceType::Bond => Interface::Bond({
            let mut iface = BondInterface::new();
            iface.base = base_iface;
            iface
        }),
        InterfaceType::Vlan => Interface::Vlan({
            let mut iface = VlanInterface::new();
            iface.base = base_iface;
            iface
        }),
        InterfaceType::Vxlan => Interface::Vxlan({
            let mut iface = VxlanInterface::new();
            iface.base = base_iface;
            iface
        }),
        InterfaceType::MacVlan => Interface::MacVlan({
            let mut iface = MacVlanInterface::new();
            iface.base = base_iface;
            iface
        }),
        InterfaceType::MacVtap => Interface::MacVtap({
            let mut iface = MacVtapInterface::new();
            iface.base = base_iface;
            iface
        }),
        InterfaceType::Vrf => Interface::Vrf({
            let mut iface = VrfInterface::new();
            iface.base = base_iface;
            iface
        }),
        InterfaceType::Loopback => Interface::Loopback({
            let mut iface = LoopbackInterface::new();
            iface.base = base_iface;
            iface
        }),
        InterfaceType::MacSec => Interface::MacSec({
            let mut iface = MacSecInterface::new();
            iface.base = base_iface;
            iface
        }),
        InterfaceType::Hsr => Interface::Hsr({
            let mut iface = HsrInterface::new();
            iface.base = base_iface;
            iface
        }),
        InterfaceType::InfiniBand => Interface::InfiniBand({
            InfiniBandInterface {
                base: base_iface,
                ..Default::default()
            }
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
                Interface::Loopback(iface)
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
                Interface::Unknown(iface)
            }
        }
    };
    Some(iface)
}

fn get_identifier(nm_conn: &NmConnection) -> InterfaceIdentifier {
    if let Some(nm_set) = nm_conn.wired.as_ref() {
        if nm_set
            .mac_address
            .as_ref()
            .map(|a| !a.is_empty())
            .unwrap_or_default()
        {
            return InterfaceIdentifier::MacAddress;
        }
    }

    InterfaceIdentifier::Name
}

fn get_connection_name(nm_conn: &NmConnection) -> Option<String> {
    if let Some(nm_set) = nm_conn.connection.as_ref() {
        return nm_set.id.clone();
    }
    None
}
