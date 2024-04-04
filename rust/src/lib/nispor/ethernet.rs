use crate::{
    BaseInterface, EthernetConfig, EthernetDuplex, EthernetInterface,
    SrIovConfig, SrIovVfConfig, VlanProtocol,
};
use std::{fs, path};

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
    if let Some(sr_iov) = &mut eth_conf.sr_iov {
        let p: path::PathBuf = [
            "/sys/class/net",
            &np_iface.name,
            "device/sriov_drivers_autoprobe",
        ]
        .iter()
        .collect();
        if let Ok(contents) = fs::read_to_string(&p) {
            match contents.as_str().trim().parse::<u8>() {
                Ok(i) => {
                    sr_iov.drivers_autoprobe = Some(i == 1);
                }
                Err(err) => {
                    log::warn!(
                        "failed to parse {}: {:?}",
                        p.to_string_lossy(),
                        err
                    );
                }
            }
        }
    }
    if let Some(ethtool_info) = &np_iface.ethtool {
        if let Some(link_mode_info) = &ethtool_info.link_mode {
            if link_mode_info.speed > 0 {
                eth_conf.speed = Some(link_mode_info.speed);
            }
            eth_conf.auto_neg = Some(link_mode_info.auto_negotiate);
            match link_mode_info.duplex {
                nispor::EthtoolLinkModeDuplex::Full => {
                    eth_conf.duplex = Some(EthernetDuplex::Full);
                }
                nispor::EthtoolLinkModeDuplex::Half => {
                    eth_conf.duplex = Some(EthernetDuplex::Half);
                }
                _ => (),
            }
        }
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
        vf.vlan_id = Some(vf_info.vlan_id);
        vf.qos = Some(vf_info.qos);
        vf.vlan_proto = match &vf_info.vlan_proto {
            nispor::VlanProtocol::Ieee8021Q => Some(VlanProtocol::Ieee8021Q),
            nispor::VlanProtocol::Ieee8021AD => Some(VlanProtocol::Ieee8021Ad),
            p => {
                log::warn!(
                    "Got unknown VLAN protocol {p:?} on SR-IOV VF {}",
                    vf_info.id
                );
                None
            }
        };
        vfs.push(vf);
    }
    ret.total_vfs = Some(vfs.len() as u32);
    ret.vfs = Some(vfs);
    ret
}
