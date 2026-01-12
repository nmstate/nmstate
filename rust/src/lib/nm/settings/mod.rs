// SPDX-License-Identifier: Apache-2.0

mod bond;
mod bridge;
mod connection;
mod dns;
mod ethtool;
mod hsr;
mod ieee8021x;
mod iface_match;
mod infiniband;
mod ip;
mod ipvlan;
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

#[cfg(feature = "query_apply")]
pub(crate) use self::bond::get_bond_balance_slb;
#[cfg(feature = "gen_conf")]
pub(crate) use self::connection::uuid_from_name_and_type;
#[cfg(feature = "query_apply")]
pub(crate) use self::user::NMSTATE_DESCRIPTION;
pub(crate) use self::{
    connection::iface_to_nm_connections, ip::fix_ip_dhcp_timeout,
};
