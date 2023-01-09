// SPDX-License-Identifier: Apache-2.0

mod apply;
mod dns;
mod ieee8021x;
mod ip;
mod lldp;
mod mptcp;
mod ovs;
mod profile;
mod route;
mod user;
mod veth;
mod vlan;
mod vrf;
mod vxlan;

pub(crate) use self::apply::nm_apply;
pub(crate) use self::dns::retrieve_dns_info;
pub(crate) use self::ieee8021x::nm_802_1x_to_nmstate;
pub(crate) use self::ip::{
    nm_ip_setting_to_nmstate4, nm_ip_setting_to_nmstate6, query_nmstate_wait_ip,
};
pub(crate) use self::lldp::{get_lldp, is_lldp_enabled};
pub(crate) use self::mptcp::{is_mptcp_flags_changed, is_mptcp_supported};
pub(crate) use self::ovs::delete_orphan_ovs_ports;
pub(crate) use self::profile::{
    activate_nm_profiles, create_index_for_nm_conns_by_name_type,
    deactivate_nm_profiles, delete_exist_profiles, save_nm_profiles,
};
pub(crate) use self::route::is_route_removed;
pub(crate) use self::user::get_description;
pub(crate) use self::veth::is_veth_peer_changed;
pub(crate) use self::vlan::is_vlan_id_changed;
pub(crate) use self::vrf::is_vrf_table_id_changed;
pub(crate) use self::vxlan::is_vxlan_id_changed;
