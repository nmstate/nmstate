use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Eq, PartialEq, Clone, Default)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
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
#[serde(deny_unknown_fields)]
pub struct EthtoolPauseConfig {
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub rx: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub tx: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
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
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "rx",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub rx_checksum: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "gro",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub rx_gro: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "lro",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub rx_lro: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "rxvlan",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub rx_vlan_hw_parse: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "txvlan",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub tx_vlan_hw_insert: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "ntuple",
        alias = "ntuple-filters",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub rx_ntuple_filter: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "rxhash",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub rx_hashing: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub tx_scatter_gather: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub tx_tcp_segmentation: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        alias = "generic-segmentation-offload",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
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
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct EthtoolCoalesceConfig {
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub adaptive_rx: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_bool_or_string"
    )]
    pub adaptive_tx: Option<bool>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub pkt_rate_high: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub pkt_rate_low: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_frames: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_frames_high: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_frames_irq: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_frames_low: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_usecs: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_usecs_high: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_usecs_irq: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_usecs_low: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub sample_interval: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub stats_block_usecs: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub tx_frames: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub tx_frames_high: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub tx_frames_irq: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub tx_frames_low: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub tx_usecs: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub tx_usecs_high: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub tx_usecs_irq: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub tx_usecs_low: Option<u32>,
}

impl EthtoolCoalesceConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Serialize, Deserialize, Debug, Eq, PartialEq, Clone, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct EthtoolRingConfig {
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_max: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_jumbo: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_jumbo_max: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_mini: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub rx_mini_max: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub tx: Option<u32>,
    #[serde(
        skip_serializing_if = "Option::is_none",
        default,
        deserialize_with = "crate::deserializer::option_u32_or_string"
    )]
    pub tx_max: Option<u32>,
}

impl EthtoolRingConfig {
    pub fn new() -> Self {
        Self::default()
    }
}
