// SPDX-License-Identifier: Apache-2.0

use crate::{BaseInterface, IpVlanConfig, IpVlanInterface, IpVlanMode};

pub(crate) fn np_ipvlan_to_nmstate(
    np_iface: &nispor::Iface,
    base_iface: BaseInterface,
) -> IpVlanInterface {
    let ipvlan_conf =
        np_iface
            .ip_vlan
            .as_ref()
            .map(|np_ipvlan_info| IpVlanConfig {
                mode: match &np_ipvlan_info.mode {
                    nispor::IpVlanMode::L2 => Some(IpVlanMode::L2),
                    nispor::IpVlanMode::L3 => Some(IpVlanMode::L3),
                    nispor::IpVlanMode::L3S => Some(IpVlanMode::L3S),
                    _ => {
                        log::warn!(
                            "Unknown supported IPVLAN mode {:?}",
                            np_ipvlan_info.mode
                        );
                        Some(IpVlanMode::L3)
                    }
                },
                private: Some(
                    np_ipvlan_info.flags.contains(&nispor::IpVlanFlag::Private),
                ),
                vepa: Some(
                    np_ipvlan_info.flags.contains(&nispor::IpVlanFlag::Vepa),
                ),
                base_iface: Some(np_ipvlan_info.base_iface.clone()),
            });

    IpVlanInterface {
        base: base_iface,
        ipvlan: ipvlan_conf,
    }
}
