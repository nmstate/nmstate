// SPDX-License-Identifier: Apache-2.0

use crate::{
    BaseInterface, VlanConfig, VlanInterface, VlanProtocol,
    VlanRegistrationProtocol,
};

pub(crate) fn np_vlan_to_nmstate(
    np_iface: &nispor::Iface,
    base_iface: BaseInterface,
) -> VlanInterface {
    let vlan_conf = np_iface.vlan.as_ref().map(|np_vlan_info| VlanConfig {
        id: np_vlan_info.vlan_id,
        base_iface: np_vlan_info.base_iface.clone(),
        protocol: match &np_vlan_info.protocol {
            nispor::VlanProtocol::Ieee8021Q => Some(VlanProtocol::Ieee8021Q),
            nispor::VlanProtocol::Ieee8021AD => Some(VlanProtocol::Ieee8021Ad),
            p => {
                log::warn!(
                    "Got unknown VLAN protocol {p:?} on VLAN iface {}",
                    np_iface.name.as_str()
                );
                None
            }
        },
        reorder_headers: Some(np_vlan_info.is_reorder_hdr),
        loose_binding: Some(np_vlan_info.is_loose_binding),
        // They are mutually exclusive, vlan cannot be gvrp and mvrp at the
        // same time
        registration_protocol: if np_vlan_info.is_gvrp {
            Some(VlanRegistrationProtocol::Gvrp)
        } else if np_vlan_info.is_mvrp {
            Some(VlanRegistrationProtocol::Mvrp)
        } else {
            Some(VlanRegistrationProtocol::None)
        },
    });

    VlanInterface {
        base: base_iface,
        vlan: vlan_conf,
    }
}

pub(crate) fn nms_vlan_conf_to_np(
    nms_vlan_conf: Option<&VlanConfig>,
) -> Option<nispor::VlanConf> {
    nms_vlan_conf.map(|nms_vlan_conf| {
        let mut np_vlan_conf = nispor::VlanConf::default();
        np_vlan_conf.vlan_id = nms_vlan_conf.id;
        np_vlan_conf.base_iface = nms_vlan_conf.base_iface.clone();
        np_vlan_conf
    })
}
