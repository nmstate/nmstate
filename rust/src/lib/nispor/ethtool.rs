use crate::{
    EthtoolCoalesceConfig, EthtoolConfig, EthtoolFeatureConfig,
    EthtoolPauseConfig, EthtoolRingConfig,
};

pub(crate) fn np_ethtool_to_nmstate(
    np_iface: &nispor::Iface,
) -> Option<EthtoolConfig> {
    if let Some(ethtool_info) = &np_iface.ethtool {
        return Some(gen_ethtool_config(ethtool_info));
    }

    None
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
    if let Some(feature) = &ethtool_info.features {
        let mut feature_config = EthtoolFeatureConfig::new();
        let changeable = &feature.changeable;
        if let Some(rx_checksum) = changeable.get("rx-checksum") {
            feature_config.rx_checksum = Some(*rx_checksum);
        }
        if let Some(tx_generic_segmentation) =
            changeable.get("tx-generic-segmentation")
        {
            feature_config.tx_generic_segmentation =
                Some(*tx_generic_segmentation);
        }
        if let Some(rx_gro) = changeable.get("rx-gro") {
            feature_config.rx_gro = Some(*rx_gro);
        }
        if let Some(rx_lro) = changeable.get("rx-lro") {
            feature_config.rx_lro = Some(*rx_lro);
        }
        if let Some(rx_vlan_hw_parse) = changeable.get("rx-vlan-hw-parse") {
            feature_config.rx_vlan_hw_parse = Some(*rx_vlan_hw_parse);
        }
        if let Some(tx_vlan_hw_insert) = changeable.get("tx-vlan-hw-insert") {
            feature_config.tx_vlan_hw_insert = Some(*tx_vlan_hw_insert);
        }
        if let Some(rx_ntuple_filter) = changeable.get("rx-ntuple-filter") {
            feature_config.rx_ntuple_filter = Some(*rx_ntuple_filter);
        }
        if let Some(rx_hashing) = changeable.get("rx-hashing") {
            feature_config.rx_hashing = Some(*rx_hashing);
        }
        if let Some(tx_scatter_gather) = changeable.get("tx-scatter-gather") {
            feature_config.tx_scatter_gather = Some(*tx_scatter_gather);
        }
        if let Some(tx_tcp_segmentation) = changeable.get("tx-tcp-segmentation")
        {
            feature_config.tx_tcp_segmentation = Some(*tx_tcp_segmentation);
        }
        ret.feature = Some(feature_config);
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
    ret
}
