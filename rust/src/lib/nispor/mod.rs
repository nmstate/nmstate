// SPDX-License-Identifier: Apache-2.0

mod alt_name;
mod apply;
mod base_iface;
mod bond;
mod dns;
mod error;
mod ethernet;
mod ethtool;
mod hostname;
mod hsr;
mod infiniband;
mod ip;
mod ip_tunnel;
mod ipvlan;
mod linux_bridge;
mod linux_bridge_port_vlan;
mod mac_vlan;
mod macsec;
mod mptcp;
mod route;
mod route_rule;
mod show;
mod veth;
mod vlan;
mod vrf;
mod vxlan;

pub(crate) use apply::nispor_apply;
pub(crate) use hostname::set_running_hostname;
pub(crate) use ip::{collect_ifa_proto_addrs, restore_ifa_proto_addrs};
#[cfg(test)]
pub(crate) use ip::{nmstate_addr_to_conf, strip_query_only_fields};
pub(crate) use show::nispor_retrieve;

pub(crate) use self::alt_name::{
    apply_ifaces_alt_names, persist_alt_name_config,
};
