// SPDX-License-Identifier: Apache-2.0

mod base;
mod bond;
mod dispatch;
mod dns;
mod ethernet;
mod hostname;
mod hsr;
mod iface;
mod infiniband;
mod inter_ifaces;
mod ip;
mod ipsec;
mod linux_bridge;
mod mac_vlan;
mod mac_vtap;
mod macsec;
mod mptcp;
mod net_state;
pub(crate) mod ovn;
mod ovs;
mod route;
mod route_rule;
mod sriov;
mod vlan;
mod vrf;
mod vxlan;

#[cfg(test)]
pub(crate) use route::is_route_delayed_by_nm;
