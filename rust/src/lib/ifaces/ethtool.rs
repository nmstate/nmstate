use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Eq, PartialEq, Clone, Default)]
#[non_exhaustive]
pub struct EthtoolConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pause: Option<EthtoolPauseConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub feature: Option<EthtoolFeatureConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub coalesce: Option<EthtoolCoalesceConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ring: Option<EthtoolRingConfig>,
}

impl EthtoolConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(
    Serialize, Deserialize, Debug, Eq, PartialEq, Clone, Default, Copy,
)]
#[non_exhaustive]
pub struct EthtoolPauseConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub autoneg: Option<bool>,
}

impl EthtoolPauseConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(
    Serialize, Deserialize, Debug, Eq, PartialEq, Clone, Default, Copy,
)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct EthtoolFeatureConfig {
    #[serde(skip_serializing_if = "Option::is_none", alias = "rx")]
    pub rx_checksum: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none", alias = "gro")]
    pub rx_gro: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none", alias = "lro")]
    pub rx_lro: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none", alias = "rxvlan")]
    pub rx_vlan_hw_parse: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none", alias = "txvlan")]
    pub tx_vlan_hw_insert: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "ntuple",
        alias = "ntuple-filters"
    )]
    pub rx_ntuple_filter: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none", alias = "rxhash")]
    pub rx_hashing: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_scatter_gather: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_tcp_segmentation: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "generic-segmentation-offload"
    )]
    pub tx_generic_segmentation: Option<bool>,
}

impl EthtoolFeatureConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(
    Serialize, Deserialize, Debug, Eq, PartialEq, Clone, Default, Copy,
)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct EthtoolCoalesceConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adaptive_rx: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adaptive_tx: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pkt_rate_high: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pkt_rate_low: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_frames: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_frames_high: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_frames_irq: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_frames_low: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_usecs: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_usecs_high: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_usecs_irq: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_usecs_low: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sample_interval: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stats_block_usecs: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_frames: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_frames_high: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_frames_irq: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_frames_low: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_usecs: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_usecs_high: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_usecs_irq: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_usecs_low: Option<u32>,
}

impl EthtoolCoalesceConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Serialize, Deserialize, Debug, Eq, PartialEq, Clone, Default)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub struct EthtoolRingConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_max: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_jumbo: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_jumbo_max: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_mini: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_mini_max: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_max: Option<u32>,
}

impl EthtoolRingConfig {
    pub fn new() -> Self {
        Self::default()
    }
}
