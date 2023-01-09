// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{NmConnection, NmSettingVeth};

use super::{
    connection::{
        gen_nm_conn_setting, NM_SETTING_VETH_SETTING_NAME,
        NM_SETTING_WIRED_SETTING_NAME,
    },
    ip::gen_nm_ip_setting,
};

use crate::{
    BaseInterface, EthernetInterface, Interface, InterfaceIpv4, InterfaceIpv6,
    InterfaceState, InterfaceType, NmstateError, VethConfig,
};

impl From<&VethConfig> for NmSettingVeth {
    fn from(config: &VethConfig) -> Self {
        let mut settings = NmSettingVeth::default();
        settings.peer = Some(config.peer.to_string());
        settings
    }
}

pub(crate) fn create_veth_peer_profile_if_not_found(
    peer_name: &str,
    end_name: &str,
    exist_nm_conns: &[NmConnection],
    stable_uuid: bool,
) -> Result<NmConnection, NmstateError> {
    for nm_conn in exist_nm_conns {
        if let Some(iface_type) = nm_conn.iface_type() {
            if nm_conn.iface_name() == Some(peer_name)
                && [NM_SETTING_WIRED_SETTING_NAME, NM_SETTING_VETH_SETTING_NAME]
                    .contains(&iface_type)
            {
                return Ok(nm_conn.clone());
            }
        }
    }
    // Create new connection
    let mut eth_iface = EthernetInterface::new();
    eth_iface.base = BaseInterface {
        name: peer_name.to_string(),
        iface_type: InterfaceType::Veth,
        state: InterfaceState::Up,
        ipv4: Some(InterfaceIpv4::new()),
        ipv6: Some(InterfaceIpv6::new()),
        ..Default::default()
    };
    let iface = Interface::Ethernet(eth_iface);
    let mut nm_conn = NmConnection::default();
    gen_nm_conn_setting(&iface, &mut nm_conn, stable_uuid)?;
    gen_nm_ip_setting(&iface, None, &mut nm_conn)?;
    nm_conn.veth = Some(NmSettingVeth::from(&VethConfig {
        peer: end_name.to_string(),
    }));
    Ok(nm_conn)
}
