// SPDX-License-Identifier: Apache-2.0

use std::{
    collections::{HashMap, HashSet},
    sync::OnceLock,
};

use crate::{
    EthtoolCoalesceConfig, EthtoolConfig, EthtoolFecConfig, EthtoolFecMode,
    EthtoolPauseConfig, EthtoolRingConfig,
};

static SUPPORTED_ETHTOOL_FEATURES: OnceLock<HashSet<&'static str>> =
    OnceLock::new();

// The list of ethtool features supported by NetworkManager
const _SUPPORTED_ETHTOOL_FEATURES: [&str; 55] = [
    "esp-hw-offload",
    "esp-tx-csum-hw-offload",
    "fcoe-mtu",
    "highdma",
    "hw-tc-offload",
    "l2-fwd-offload",
    "loopback",
    "macsec-hw-offload",
    "rx-all",
    "rx-checksum",
    "rx-fcs",
    "rx-gro",
    "rx-gro-hw",
    "rx-gro-list",
    "rx-hashing",
    "rx-lro",
    "rx-ntuple-filter",
    "rx-udp-gro-forwarding",
    "rx-udp_tunnel-port-offload",
    "rx-vlan-filter",
    "rx-vlan-hw-parse",
    "rx-vlan-stag-filter",
    "rx-vlan-stag-hw-parse",
    "tls-hw-record",
    "tls-hw-rx-offload",
    "tls-hw-tx-offload",
    "tx-checksum-fcoe-crc",
    "tx-checksum-ip-generic",
    "tx-checksum-ipv4",
    "tx-checksum-ipv6",
    "tx-checksum-sctp",
    "tx-esp-segmentation",
    "tx-fcoe-segmentation",
    "tx-generic-segmentation",
    "tx-gre-csum-segmentation",
    "tx-gre-segmentation",
    "tx-gso-list",
    "tx-gso-partial",
    "tx-gso-robust",
    "tx-ipxip4-segmentation",
    "tx-ipxip6-segmentation",
    "tx-nocache-copy",
    "tx-scatter-gather",
    "tx-scatter-gather-fraglist",
    "tx-sctp-segmentation",
    "tx-tcp-ecn-segmentation",
    "tx-tcp-mangleid-segmentation",
    "tx-tcp-segmentation",
    "tx-tcp6-segmentation",
    "tx-tunnel-remcsum-segmentation",
    "tx-udp-segmentation",
    "tx-udp_tnl-csum-segmentation",
    "tx-udp_tnl-segmentation",
    "tx-vlan-hw-insert",
    "tx-vlan-stag-hw-insert",
];

pub(crate) fn np_ethtool_to_nmstate(
    np_iface: &nispor::Iface,
) -> Option<EthtoolConfig> {
    np_iface.ethtool.as_ref().map(gen_ethtool_config)
}

fn gen_ethtool_config(ethtool_info: &nispor::EthtoolInfo) -> EthtoolConfig {
    let mut ret = EthtoolConfig::new();
    if let Some(pause) = &ethtool_info.pause {
        let mut pause_config = EthtoolPauseConfig::new();
        pause_config.rx = Some(pause.rx);
        pause_config.tx = Some(pause.tx);
        pause_config.autoneg = Some(pause.auto_negotiate);
        ret.pause = Some(pause_config);
    }

    let supported_features = SUPPORTED_ETHTOOL_FEATURES
        .get_or_init(|| _SUPPORTED_ETHTOOL_FEATURES.iter().copied().collect());

    if let Some(feature) = &ethtool_info.features {
        ret.feature = Some(
            feature
                .changeable
                .iter()
                .filter_map(|(name, value)| {
                    if supported_features.contains(&name.as_str()) {
                        Some((name.to_string(), *value))
                    } else {
                        None
                    }
                })
                .collect::<HashMap<String, bool>>()
                .into(),
        );
    }
    if let Some(coalesce) = &ethtool_info.coalesce {
        let mut coalesce_config = EthtoolCoalesceConfig::new();
        coalesce_config.pkt_rate_high = coalesce.pkt_rate_high;
        coalesce_config.pkt_rate_low = coalesce.pkt_rate_low;
        coalesce_config.sample_interval = coalesce.rate_sample_interval;
        coalesce_config.rx_frames = coalesce.rx_max_frames;
        coalesce_config.rx_frames_high = coalesce.rx_max_frames_high;
        coalesce_config.rx_frames_low = coalesce.rx_max_frames_low;
        coalesce_config.rx_usecs = coalesce.rx_usecs;
        coalesce_config.rx_usecs_high = coalesce.rx_usecs_high;
        coalesce_config.rx_usecs_irq = coalesce.rx_usecs_irq;
        coalesce_config.rx_usecs_low = coalesce.rx_usecs_low;
        coalesce_config.stats_block_usecs = coalesce.stats_block_usecs;
        coalesce_config.tx_frames = coalesce.tx_max_frames;
        coalesce_config.tx_frames_high = coalesce.tx_max_frames_high;
        coalesce_config.tx_frames_low = coalesce.tx_max_frames_low;
        coalesce_config.tx_frames_irq = coalesce.tx_max_frames_irq;
        coalesce_config.tx_usecs = coalesce.tx_usecs;
        coalesce_config.tx_usecs_high = coalesce.tx_usecs_high;
        coalesce_config.tx_usecs_low = coalesce.tx_usecs_low;
        coalesce_config.tx_usecs_irq = coalesce.tx_usecs_irq;
        coalesce_config.adaptive_rx = coalesce.use_adaptive_rx;
        coalesce_config.adaptive_tx = coalesce.use_adaptive_tx;

        ret.coalesce = Some(coalesce_config);
    }
    if let Some(ring) = &ethtool_info.ring {
        let mut ring_config = EthtoolRingConfig::new();
        ring_config.rx = ring.rx;
        ring_config.rx_max = ring.rx_max;
        ring_config.rx_jumbo = ring.rx_jumbo;
        ring_config.rx_jumbo_max = ring.rx_jumbo_max;
        ring_config.rx_mini = ring.rx_mini;
        ring_config.rx_mini_max = ring.rx_mini_max;
        ring_config.tx = ring.tx;
        ring_config.tx_max = ring.tx_max;

        ret.ring = Some(ring_config);
    }
    if let Some(fec) = &ethtool_info.fec {
        ret.fec = Some(EthtoolFecConfig {
            auto: Some(fec.auto),
            mode: np_fec_mode_to_nmstate(&fec.active),
        });
    }
    ret
}

fn np_fec_mode_to_nmstate(
    np_mode: &nispor::EthtoolFecMode,
) -> Option<EthtoolFecMode> {
    match *np_mode {
        nispor::EthtoolFecMode::Off => Some(EthtoolFecMode::Off),
        nispor::EthtoolFecMode::Rs => Some(EthtoolFecMode::Rs),
        nispor::EthtoolFecMode::Baser => Some(EthtoolFecMode::Baser),
        nispor::EthtoolFecMode::Llrs => Some(EthtoolFecMode::Llrs),
        _ => {
            log::info!("Unsupported Ethtool FEC mode {np_mode:?}");
            None
        }
    }
}
