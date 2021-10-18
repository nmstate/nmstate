use crate::{BaseInterface, VlanConfig, VlanInterface};

pub(crate) fn np_vlan_to_nmstate(
    np_iface: nispor::Iface,
    base_iface: BaseInterface,
) -> VlanInterface {
    let vlan_conf = match np_iface.vlan {
        Some(np_vlan_info) => Some(VlanConfig {
            id: np_vlan_info.vlan_id,
            base_iface: np_vlan_info.base_iface,
        }),
        None => None,
    };
    VlanInterface {
        base: base_iface,
        vlan: vlan_conf,
    }
}

pub(crate) fn nms_vlan_conf_to_np(
    nms_vlan_conf: Option<&VlanConfig>,
) -> Option<nispor::VlanConf> {
    nms_vlan_conf.map(|nms_vlan_conf| nispor::VlanConf {
        vlan_id: nms_vlan_conf.id,
        base_iface: nms_vlan_conf.base_iface.clone(),
    })
}
