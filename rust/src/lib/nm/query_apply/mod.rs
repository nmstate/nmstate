// SPDX-License-Identifier: Apache-2.0

mod apply;
mod connection;
pub(crate) mod device;
pub(crate) mod dispatch;
pub(crate) mod dns;
mod hsr;
mod ieee8021x;
mod ip;
mod ip_tunnel;
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

pub(crate) use self::{
    apply::nm_apply,
    connection::{
        activate_nm_connections, deactivate_nm_connections,
        delete_exist_connections, save_nm_connections,
    },
    device::deactivate_nm_devices,
    dns::retrieve_dns_state,
    hsr::is_hsr_changed,
    ieee8021x::nm_802_1x_to_nmstate,
    ip::{
        nm_ip_setting_to_nmstate4, nm_ip_setting_to_nmstate6,
        query_nmstate_wait_ip,
    },
    ip_tunnel::is_ip_tunnel_changed,
    ipvlan::is_ipvlan_changed,
    lldp::{get_lldp, is_lldp_enabled},
    mptcp::is_mptcp_flags_changed,
    ovs::delete_orphan_ovs_ports,
    route::is_route_removed,
    user::get_description,
    veth::is_veth_peer_changed,
    vlan::is_vlan_changed,
    vrf::is_vrf_table_id_changed,
    vxlan::is_vxlan_changed,
};
