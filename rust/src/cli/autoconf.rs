// SPDX-License-Identifier: Apache-2.0

use std::collections::hash_map::Entry;
use std::collections::HashMap;

use nmstate::{
    BaseInterface, BondConfig, BondInterface, BondMode, BondPortConfig,
    Interface, InterfaceState, InterfaceType, Interfaces, LldpNeighborTlv,
    NetworkState, VlanConfig, VlanInterface,
};

use crate::error::CliError;

const APP_NAME: &str = "nmstatectl-autoconf";
const BOND_PREFIX: &str = "bond";

pub(crate) fn autoconf(argv: &[String]) -> Result<String, CliError> {
    let matches = clap::Command::new(APP_NAME)
        .version(clap::crate_version!())
        .author("Gris Ge <fge@redhat.com>")
        .about("Network Auto-Configure using LLDP information")
        .arg(
            clap::Arg::new("DRY_RUN")
                .long("dry-run")
                .short('d')
                .takes_value(false)
                .help(
                    "Generate the network state that is going to be \
                    applied and print it out without applying any change.",
                ),
        )
        .arg(
            clap::Arg::new("ONLY")
                .index(1)
                .help("Use only the specified NICs (comma-separated)"),
        )
        .get_matches_from(argv);
    let mut log_builder = env_logger::Builder::new();

    log_builder.filter(Some("autoconf"), log::LevelFilter::Info);
    log_builder.filter(Some("nmstate"), log::LevelFilter::Info);
    log_builder.filter(Some("nm_dbus"), log::LevelFilter::Info);
    log_builder.init();

    let mut cur_state = NetworkState::new();
    cur_state.retrieve()?;
    filter_net_state(&mut cur_state, matches.value_of("ONLY"))?;

    let vlan_to_iface = get_lldp_vlans(&cur_state);

    let desire_state = gen_desire_state(&vlan_to_iface);

    if !matches.is_present("DRY_RUN") {
        eprintln!("This is a experimental function!");
        desire_state.apply()?;
    }
    Ok(serde_yaml::to_string(&desire_state)?)
}

fn filter_net_state(
    net_state: &mut NetworkState,
    filters: Option<&str>,
) -> Result<(), CliError> {
    if let Some(filters) = filters {
        let mut new_ifaces = Interfaces::new();
        for filter in filters.split(',') {
            if let Some(iface) = net_state
                .interfaces
                .get_iface(filter, InterfaceType::Unknown)
            {
                new_ifaces.push(iface.clone());
            } else {
                return Err(CliError {
                    code: crate::error::EX_DATAERR,
                    error_msg: format!("Interface {filter} not found"),
                });
            }
        }
        net_state.interfaces = new_ifaces;
    }
    Ok(())
}

// Return HashMap:
//  key:  (vlan_id, vlan_name)
//  value: Vec<interface_name>
fn get_lldp_vlans(net_state: &NetworkState) -> HashMap<(u32, &str), Vec<&str>> {
    let mut ret: HashMap<(u32, &str), Vec<&str>> = HashMap::new();
    for iface in net_state.interfaces.to_vec() {
        if let Some(lldp_neighbors) = iface
            .base_iface()
            .lldp
            .as_ref()
            .map(|l| l.neighbors.as_slice())
        {
            if lldp_neighbors.is_empty() {
                continue;
            }
            for lldp_tlvs in lldp_neighbors {
                for lldp_tlv in lldp_tlvs {
                    if let LldpNeighborTlv::Ieee8021Vlans(lldp_vlans) = lldp_tlv
                    {
                        for lldp_vlan in &lldp_vlans.ieee_802_1_vlans {
                            match ret
                                .entry((lldp_vlan.vid, lldp_vlan.name.as_str()))
                            {
                                Entry::Occupied(o) => {
                                    o.into_mut().push(iface.name());
                                }
                                Entry::Vacant(v) => {
                                    v.insert(vec![iface.name()]);
                                }
                            };
                        }
                    }
                }
            }
        }
    }
    ret
}

fn gen_desire_state(
    lldp_vlan_info: &HashMap<(u32, &str), Vec<&str>>,
) -> NetworkState {
    let mut ret = NetworkState::new();
    for ((vid, name), ifaces) in lldp_vlan_info.iter() {
        if ifaces.len() > 1 {
            let bond_iface_name = format!("{BOND_PREFIX}{vid}");
            ret.append_interface_data(gen_bond_iface(&bond_iface_name, ifaces));
            ret.append_interface_data(gen_vlan_iface(
                name,
                *vid,
                &bond_iface_name,
            ));
        } else if let Some(iface) = ifaces.first() {
            ret.append_interface_data(gen_vlan_iface(name, *vid, iface));
        }
    }
    ret
}

fn gen_bond_iface(bond_name: &str, ifaces: &[&str]) -> Interface {
    let mut base_iface = BaseInterface::new();
    base_iface.name = bond_name.to_string();
    base_iface.iface_type = InterfaceType::Bond;
    base_iface.state = InterfaceState::Up;
    let mut bond_conf = BondConfig::new();
    bond_conf.mode = Some(BondMode::RoundRobin);
    bond_conf.port = Some(ifaces.iter().map(|i| i.to_string()).collect());
    let mut port_confs: Vec<BondPortConfig> = Vec::new();
    for port_name in ifaces.iter().map(|i| i.to_string()) {
        let mut port_conf = BondPortConfig::new();
        port_conf.name = port_name;
        port_confs.push(port_conf);
    }
    bond_conf.ports_config = Some(port_confs);
    let mut bond_iface = BondInterface::new();
    bond_iface.base = base_iface;
    bond_iface.bond = Some(bond_conf);
    Interface::Bond(Box::new(bond_iface))
}

fn gen_vlan_iface(vlan_name: &str, id: u32, parent: &str) -> Interface {
    let mut base_iface = BaseInterface::new();
    base_iface.name = vlan_name.to_string();
    base_iface.iface_type = InterfaceType::Vlan;
    base_iface.state = InterfaceState::Up;
    let mut vlan_conf = VlanConfig::default();
    vlan_conf.base_iface = Some(parent.to_string());
    vlan_conf.id = id.try_into().unwrap();
    let mut vlan_iface = VlanInterface::new();
    vlan_iface.base = base_iface;
    vlan_iface.vlan = Some(vlan_conf);
    Interface::Vlan(Box::new(vlan_iface))
}
