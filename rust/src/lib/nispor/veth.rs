use crate::{BaseInterface, EthernetInterface, VethConfig};

pub(crate) fn np_veth_to_nmstate(
    np_iface: &nispor::Iface,
    base_iface: BaseInterface,
) -> EthernetInterface {
    let veth_conf = np_iface.veth.as_ref().map(|np_veth_info| VethConfig {
        peer: np_veth_info.peer.clone(),
    });

    EthernetInterface {
        base: base_iface,
        veth: veth_conf,
        // TODO: Filling the ethernet section
        ..Default::default()
    }
}

pub(crate) fn nms_veth_conf_to_np(
    nms_veth_conf: Option<&VethConfig>,
) -> Option<nispor::VethConf> {
    nms_veth_conf.map(|nms_veth_conf| nispor::VethConf {
        peer: nms_veth_conf.peer.to_string(),
    })
}
