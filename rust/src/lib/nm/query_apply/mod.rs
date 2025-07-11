// SPDX-License-Identifier: Apache-2.0

mod apply;
mod connection;
pub(crate) mod device;
pub(crate) mod dispatch;
pub(crate) mod dns;
mod ieee8021x;
mod ip;
mod ipvlan;
mod lldp;
mod mptcp;
pub(crate) mod ovs;
mod route;
mod user;
mod veth;
mod vlan;
pub(crate) mod vpn;
mod vrf;
mod vxlan;

pub(crate) use self::apply::nm_apply;
pub(crate) use self::connection::{
    activate_nm_connections, deactivate_nm_connections,
    delete_exist_connections, save_nm_connections,
};
pub(crate) use self::dns::retrieve_dns_info;
pub(crate) use self::ieee8021x::nm_802_1x_to_nmstate;
pub(crate) use self::ip::{
    is_forwarding_supported, nm_ip_setting_to_nmstate4,
    nm_ip_setting_to_nmstate6, query_nmstate_wait_ip,
};
pub(crate) use self::ipvlan::is_ipvlan_changed;
pub(crate) use self::lldp::{get_lldp, is_lldp_enabled};
pub(crate) use self::mptcp::is_mptcp_flags_changed;
pub(crate) use self::ovs::delete_orphan_ovs_ports;
pub(crate) use self::route::is_route_removed;
pub(crate) use self::user::get_description;
pub(crate) use self::veth::is_veth_peer_changed;
pub(crate) use self::vlan::is_vlan_changed;
pub(crate) use self::vrf::is_vrf_table_id_changed;
pub(crate) use self::vxlan::is_vxlan_changed;
