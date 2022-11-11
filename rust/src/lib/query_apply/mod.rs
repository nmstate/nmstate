// SPDX-License-Identifier: Apache-2.0

mod base;
mod bond;
mod bridge_vlan;
mod dns;
mod ethernet;
mod hostname;
mod iface;
mod infiniband;
mod inter_ifaces;
mod ip;
mod linux_bridge;
mod lldp;
mod mac_vlan;
mod mac_vtap;
mod mptcp;
mod net_state;
mod ovs;
mod route;
mod sriov;
mod vlan;
mod vrf;
mod vxlan;

pub(crate) use self::inter_ifaces::get_ignored_ifaces;
