use std::collections::HashMap;
use std::convert::TryFrom;

use serde::Deserialize;

use super::super::{connection::DbusDictionary, NmError};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingEthtool {
    pub pause_rx: Option<bool>,
    pub pause_tx: Option<bool>,
    pub pause_autoneg: Option<bool>,
    pub coalesce_adaptive_rx: Option<bool>,
    pub coalesce_adaptive_tx: Option<bool>,
    pub coalesce_pkt_rate_high: Option<u32>,
    pub coalesce_pkt_rate_low: Option<u32>,
    pub coalesce_rx_frames: Option<u32>,
    pub coalesce_rx_frames_high: Option<u32>,
    pub coalesce_rx_frames_low: Option<u32>,
    pub coalesce_rx_frames_irq: Option<u32>,
    pub coalesce_rx_usecs: Option<u32>,
    pub coalesce_rx_usecs_high: Option<u32>,
    pub coalesce_rx_usecs_low: Option<u32>,
    pub coalesce_rx_usecs_irq: Option<u32>,
    pub coalesce_sample_interval: Option<u32>,
    pub coalesce_stats_block_usecs: Option<u32>,
    pub coalesce_tx_frames: Option<u32>,
    pub coalesce_tx_frames_high: Option<u32>,
    pub coalesce_tx_frames_low: Option<u32>,
    pub coalesce_tx_frames_irq: Option<u32>,
    pub coalesce_tx_usecs: Option<u32>,
    pub coalesce_tx_usecs_high: Option<u32>,
    pub coalesce_tx_usecs_low: Option<u32>,
    pub coalesce_tx_usecs_irq: Option<u32>,
    pub feature_rx: Option<bool>,
    pub feature_sg: Option<bool>,
    pub feature_tso: Option<bool>,
    pub feature_gro: Option<bool>,
    pub feature_gso: Option<bool>,
    pub feature_highdma: Option<bool>,
    pub feature_rxhash: Option<bool>,
    pub feature_lro: Option<bool>,
    pub feature_ntuple: Option<bool>,
    pub feature_rxvlan: Option<bool>,
    pub feature_txvlan: Option<bool>,
    pub ring_rx: Option<u32>,
    pub ring_rx_jumbo: Option<u32>,
    pub ring_rx_mini: Option<u32>,
    pub ring_tx: Option<u32>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingEthtool {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            pause_rx: _from_map!(v, "pause-rx", bool::try_from)?,
            pause_tx: _from_map!(v, "pause-tx", bool::try_from)?,
            pause_autoneg: _from_map!(v, "pause-autoneg", bool::try_from)?,
            coalesce_adaptive_rx: _from_map!(
                v,
                "coalesce-adaptive-rx",
                bool::try_from
            )?,
            coalesce_adaptive_tx: _from_map!(
                v,
                "coalesce-adaptive-tx",
                bool::try_from
            )?,
            coalesce_pkt_rate_high: _from_map!(
                v,
                "coalesce-pkt-rate-high",
                u32::try_from
            )?,
            coalesce_pkt_rate_low: _from_map!(
                v,
                "coalesce-pkt-rate-low",
                u32::try_from
            )?,
            coalesce_rx_frames: _from_map!(
                v,
                "coalesce-rx-frames",
                u32::try_from
            )?,
            coalesce_rx_frames_high: _from_map!(
                v,
                "coalesce-rx-frames-high",
                u32::try_from
            )?,
            coalesce_rx_frames_low: _from_map!(
                v,
                "coalesce-rx-frames-low",
                u32::try_from
            )?,
            coalesce_rx_frames_irq: _from_map!(
                v,
                "coalesce-rx-frames-irq",
                u32::try_from
            )?,
            coalesce_rx_usecs: _from_map!(
                v,
                "coalesce-rx-usecs",
                u32::try_from
            )?,
            coalesce_rx_usecs_high: _from_map!(
                v,
                "coalesce-rx-usecs-high",
                u32::try_from
            )?,
            coalesce_rx_usecs_low: _from_map!(
                v,
                "coalesce-rx-usecs-low",
                u32::try_from
            )?,
            coalesce_rx_usecs_irq: _from_map!(
                v,
                "coalesce-rx-usecs-irq",
                u32::try_from
            )?,
            coalesce_tx_frames: _from_map!(
                v,
                "coalesce-tx-frames",
                u32::try_from
            )?,
            coalesce_tx_frames_high: _from_map!(
                v,
                "coalesce-tx-frames-high",
                u32::try_from
            )?,
            coalesce_tx_frames_low: _from_map!(
                v,
                "coalesce-tx-frames-low",
                u32::try_from
            )?,
            coalesce_tx_frames_irq: _from_map!(
                v,
                "coalesce-tx-frames-irq",
                u32::try_from
            )?,
            coalesce_tx_usecs: _from_map!(
                v,
                "coalesce-tx-usecs",
                u32::try_from
            )?,
            coalesce_tx_usecs_high: _from_map!(
                v,
                "coalesce-tx-usecs-high",
                u32::try_from
            )?,
            coalesce_tx_usecs_low: _from_map!(
                v,
                "coalesce-tx-usecs-low",
                u32::try_from
            )?,
            coalesce_tx_usecs_irq: _from_map!(
                v,
                "coalesce-tx-usecs-irq",
                u32::try_from
            )?,
            coalesce_sample_interval: _from_map!(
                v,
                "coalesce-sample-interval",
                u32::try_from
            )?,
            coalesce_stats_block_usecs: _from_map!(
                v,
                "coalesce-stats-block-usecs",
                u32::try_from
            )?,
            feature_rx: _from_map!(v, "feature-rx", bool::try_from)?,
            feature_sg: _from_map!(v, "feature-sg", bool::try_from)?,
            feature_tso: _from_map!(v, "feature-tso", bool::try_from)?,
            feature_gro: _from_map!(v, "feature-gro", bool::try_from)?,
            feature_gso: _from_map!(v, "feature-gso", bool::try_from)?,
            feature_rxhash: _from_map!(v, "feature-rxhash", bool::try_from)?,
            feature_lro: _from_map!(v, "feature-lro", bool::try_from)?,
            feature_ntuple: _from_map!(v, "feature-ntuple", bool::try_from)?,
            feature_rxvlan: _from_map!(v, "feature-rxvlan", bool::try_from)?,
            feature_txvlan: _from_map!(v, "feature-txvlan", bool::try_from)?,
            feature_highdma: _from_map!(v, "feature-highdma", bool::try_from)?,
            ring_rx: _from_map!(v, "ring-rx", u32::try_from)?,
            ring_rx_jumbo: _from_map!(v, "ring-rx-jumbo", u32::try_from)?,
            ring_rx_mini: _from_map!(v, "ring-rx-mini", u32::try_from)?,
            ring_tx: _from_map!(v, "ring-tx", u32::try_from)?,
            _other: v,
        })
    }
}

impl NmSettingEthtool {
    pub(crate) fn to_keyfile(
        &self,
    ) -> Result<HashMap<String, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();

        for (k, v) in self.to_value()?.drain() {
            ret.insert(k.to_string(), v);
        }

        Ok(ret)
    }

    pub(crate) fn to_value(
        &self,
    ) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.pause_rx {
            ret.insert("pause-rx", zvariant::Value::new(v));
        }
        if let Some(v) = &self.pause_tx {
            ret.insert("pause-tx", zvariant::Value::new(v));
        }
        if let Some(v) = &self.pause_autoneg {
            ret.insert("pause-autoneg", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_adaptive_rx {
            ret.insert("coalesce-adaptive-rx", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_adaptive_tx {
            ret.insert("coalesce-adaptive-tx", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_pkt_rate_high {
            ret.insert("coalesce-pkt-rate-high", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_pkt_rate_low {
            ret.insert("coalesce-pkt-rate-low", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_rx_frames {
            ret.insert("coalesce-rx-frames", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_rx_frames_low {
            ret.insert("coalesce-rx-frames-low", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_rx_frames_high {
            ret.insert("coalesce-rx-frames-high", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_rx_frames_irq {
            ret.insert("coalesce-rx-frames-irq", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_tx_frames {
            ret.insert("coalesce-tx-frames", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_tx_frames_low {
            ret.insert("coalesce-tx-frames-low", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_tx_frames_high {
            ret.insert("coalesce-tx-frames-high", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_tx_frames_irq {
            ret.insert("coalesce-tx-frames-irq", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_rx_usecs {
            ret.insert("coalesce-rx-usecs", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_rx_usecs_low {
            ret.insert("coalesce-rx-usecs-low", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_rx_usecs_high {
            ret.insert("coalesce-rx-usecs-high", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_rx_usecs_irq {
            ret.insert("coalesce-rx-usecs-irq", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_tx_usecs {
            ret.insert("coalesce-tx-usecs", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_tx_usecs_low {
            ret.insert("coalesce-tx-usecs-low", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_tx_usecs_high {
            ret.insert("coalesce-tx-usecs-high", zvariant::Value::new(v));
        }
        if let Some(v) = &self.coalesce_tx_usecs_irq {
            ret.insert("coalesce-tx-usecs-irq", zvariant::Value::new(v));
        }
        if let Some(v) = &self.feature_rx {
            ret.insert("feature-rx", zvariant::Value::new(v));
        }
        if let Some(v) = &self.feature_sg {
            ret.insert("feature-sg", zvariant::Value::new(v));
        }
        if let Some(v) = &self.feature_tso {
            ret.insert("feature-tso", zvariant::Value::new(v));
        }
        if let Some(v) = &self.feature_gro {
            ret.insert("feature-gro", zvariant::Value::new(v));
        }
        if let Some(v) = &self.feature_gso {
            ret.insert("feature-gso", zvariant::Value::new(v));
        }
        if let Some(v) = &self.feature_rxhash {
            ret.insert("feature-rxhash", zvariant::Value::new(v));
        }
        if let Some(v) = &self.feature_lro {
            ret.insert("feature-lro", zvariant::Value::new(v));
        }
        if let Some(v) = &self.feature_ntuple {
            ret.insert("feature-ntuple", zvariant::Value::new(v));
        }
        if let Some(v) = &self.feature_rxvlan {
            ret.insert("feature-rxvlan", zvariant::Value::new(v));
        }
        if let Some(v) = &self.feature_txvlan {
            ret.insert("feature-txvlan", zvariant::Value::new(v));
        }
        if let Some(v) = &self.feature_highdma {
            ret.insert("feature-highdma", zvariant::Value::new(v));
        }
        if let Some(v) = &self.ring_rx {
            ret.insert("ring-rx", zvariant::Value::new(v));
        }
        if let Some(v) = &self.ring_rx_jumbo {
            ret.insert("ring-rx-jumbo", zvariant::Value::new(v));
        }
        if let Some(v) = &self.ring_rx_mini {
            ret.insert("ring-rx-mini", zvariant::Value::new(v));
        }
        if let Some(v) = &self.ring_tx {
            ret.insert("ring-tx", zvariant::Value::new(v));
        }
        Ok(ret)
    }
}
