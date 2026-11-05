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
#[cfg(test)]
pub(crate) use route_rule::{get_route_rules, get_route_rules_for_apply};
pub(crate) use route_rule::{kernel_rule_is_absent, route_rule_worker_needed};
pub(crate) use show::nispor_retrieve;

pub(crate) use self::alt_name::{
    apply_ifaces_alt_names, persist_alt_name_config,
};
