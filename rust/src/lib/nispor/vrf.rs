// SPDX-License-Identifier: Apache-2.0

use crate::{BaseInterface, VrfConfig, VrfInterface, VrfPortConfig};

pub(crate) fn np_vrf_to_nmstate(
    np_iface: &nispor::Iface,
    base_iface: BaseInterface,
) -> VrfInterface {
    let vrf_conf = np_iface.vrf.as_ref().map(|np_vrf_info| {
        let mut ports = np_vrf_info.subordinates.clone();
        ports.sort_unstable();
        let ports_config: Vec<VrfPortConfig> = ports
            .as_slice()
            .iter()
            .map(|p| VrfPortConfig {
                name: Some(p.to_string()),
                ..Default::default()
            })
            .collect();

        VrfConfig {
            table_id: np_vrf_info.table_id,
            port: Some(ports.clone()),
            ports_config: Some(ports_config),
        }
    });

    VrfInterface {
        base: base_iface,
        vrf: vrf_conf,
    }
}
