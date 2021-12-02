use crate::{
    BaseInterface, EthernetConfig, EthernetInterface, SrIovConfig,
    SrIovVfConfig,
};

pub(crate) fn np_ethernet_to_nmstate(
    np_iface: &nispor::Iface,
    base_iface: BaseInterface,
) -> EthernetInterface {
    let mut iface = EthernetInterface::new();
    iface.base = base_iface;
    iface.ethernet = Some(gen_eth_conf(np_iface));
    iface
}

fn gen_eth_conf(np_iface: &nispor::Iface) -> EthernetConfig {
    let mut eth_conf = EthernetConfig::new();
    if let Some(sriov_info) = &np_iface.sriov {
        eth_conf.sr_iov = Some(gen_sriov_conf(sriov_info));
    }

    eth_conf
}

fn gen_sriov_conf(sriov_info: &nispor::SriovInfo) -> SrIovConfig {
    let mut ret = SrIovConfig::new();
    let mut vfs: Vec<SrIovVfConfig> = Vec::new();
    for vf_info in &sriov_info.vfs {
        let mut vf = SrIovVfConfig::new();
        vf.id = vf_info.id;
        vf.iface_name =
            vf_info.iface_name.as_ref().cloned().unwrap_or_default();
        vf.mac_address = Some(vf_info.mac.to_ascii_uppercase());
        vf.spoof_check = Some(vf_info.spoof_check);
        vf.trust = Some(vf_info.trust);
        vf.min_tx_rate = Some(vf_info.min_tx_rate);
        vf.max_tx_rate = Some(vf_info.max_tx_rate);
        vfs.push(vf);
    }
    ret.total_vfs = Some(vfs.len() as u32);
    ret.vfs = Some(vfs);
    ret
}
