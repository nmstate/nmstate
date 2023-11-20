// SPDX-License-Identifier: Apache-2.0

mod bond;
mod bridge;
mod connection;
mod dns;
mod ethtool;
mod hsr;
mod ieee8021x;
mod infiniband;
mod inter_connections;
mod ip;
mod loopback;
mod mac_vlan;
mod macsec;
mod mptcp;
mod ovs;
mod route;
mod route_rule;
mod sriov;
mod user;
mod veth;
mod vlan;
mod vpn;
mod vrf;
mod vxlan;
mod wired;

pub(crate) use self::connection::{
    get_exist_profile, iface_to_nm_connections, SUPPORTED_NM_KERNEL_IFACE_TYPES,
};
#[cfg(feature = "query_apply")]
pub(crate) use self::connection::{
    iface_type_to_nm, NM_SETTING_BOND_SETTING_NAME,
    NM_SETTING_BRIDGE_SETTING_NAME, NM_SETTING_DUMMY_SETTING_NAME,
    NM_SETTING_HSR_SETTING_NAME, NM_SETTING_INFINIBAND_SETTING_NAME,
    NM_SETTING_LOOPBACK_SETTING_NAME, NM_SETTING_MACSEC_SETTING_NAME,
    NM_SETTING_MACVLAN_SETTING_NAME, NM_SETTING_OVS_BRIDGE_SETTING_NAME,
    NM_SETTING_OVS_IFACE_SETTING_NAME, NM_SETTING_OVS_PORT_SETTING_NAME,
    NM_SETTING_VETH_SETTING_NAME, NM_SETTING_VLAN_SETTING_NAME,
    NM_SETTING_VRF_SETTING_NAME, NM_SETTING_VXLAN_SETTING_NAME,
    NM_SETTING_WIRED_SETTING_NAME,
};
pub(crate) use self::inter_connections::{
    use_uuid_for_controller_reference, use_uuid_for_parent_reference,
};
pub(crate) use self::ip::fix_ip_dhcp_timeout;

#[cfg(feature = "query_apply")]
pub(crate) use self::bond::get_bond_balance_slb;
#[cfg(feature = "query_apply")]
pub(crate) use self::user::NMSTATE_DESCRIPTION;

pub(crate) use self::mptcp::remove_nm_mptcp_set;
