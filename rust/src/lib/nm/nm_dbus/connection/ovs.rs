// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::convert::TryFrom;

use serde::Deserialize;

use super::super::{connection::DbusDictionary, NmError, NmRange, ToDbusValue};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingOvsBridge {
    pub stp: Option<bool>,
    pub mcast_snooping_enable: Option<bool>,
    pub rstp: Option<bool>,
    pub fail_mode: Option<String>,
    pub datapath_type: Option<String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingOvsBridge {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            stp: _from_map!(v, "stp-enable", bool::try_from)?,
            mcast_snooping_enable: _from_map!(
                v,
                "mcast-snooping-enable",
                bool::try_from
            )?,
            rstp: _from_map!(v, "rstp-enable", bool::try_from)?,
            fail_mode: _from_map!(v, "fail-mode", String::try_from)?,
            datapath_type: _from_map!(v, "datapath-type", String::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingOvsBridge {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = self.stp {
            ret.insert("stp-enable", zvariant::Value::new(v));
        }
        if let Some(v) = self.mcast_snooping_enable {
            ret.insert("mcast-snooping-enable", zvariant::Value::new(v));
        }
        if let Some(v) = self.rstp {
            ret.insert("rstp-enable", zvariant::Value::new(v));
        }
        if let Some(v) = &self.fail_mode {
            ret.insert("fail-mode", zvariant::Value::new(v));
        }
        if let Some(v) = &self.datapath_type {
            ret.insert("datapath-type", zvariant::Value::new(v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingOvsPort {
    pub mode: Option<String>,
    pub up_delay: Option<u32>,
    pub down_delay: Option<u32>,
    pub tag: Option<u32>,
    pub vlan_mode: Option<String>,
    pub trunks: Option<Vec<NmRange>>,
    pub lacp: Option<String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingOvsPort {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            mode: _from_map!(v, "bond-mode", String::try_from)?,
            up_delay: _from_map!(v, "bond-updelay", u32::try_from)?,
            down_delay: _from_map!(v, "bond-downdelay", u32::try_from)?,
            tag: _from_map!(v, "tag", u32::try_from)?,
            vlan_mode: _from_map!(v, "vlan-mode", String::try_from)?,
            lacp: _from_map!(v, "lacp", String::try_from)?,
            trunks: _from_map!(v, "trunks", own_value_to_trunks)?,
            _other: v,
        })
    }
}

fn own_value_to_trunks(
    value: zvariant::OwnedValue,
) -> Result<Vec<NmRange>, NmError> {
    let mut ret = Vec::new();
    let raw_ranges = Vec::<DbusDictionary>::try_from(value)?;
    for raw_range in raw_ranges {
        ret.push(NmRange::try_from(raw_range)?);
    }
    Ok(ret)
}

impl ToDbusValue for NmSettingOvsPort {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.mode {
            ret.insert("bond-mode", zvariant::Value::new(v));
        }
        if let Some(v) = self.up_delay {
            ret.insert("bond-updelay", zvariant::Value::new(v));
        }
        if let Some(v) = self.down_delay {
            ret.insert("bond-downdelay", zvariant::Value::new(v));
        }
        if let Some(v) = self.tag {
            ret.insert("tag", zvariant::Value::new(v));
        }
        if let Some(v) = self.vlan_mode.as_ref() {
            ret.insert("vlan-mode", zvariant::Value::new(v));
        }
        if let Some(v) = self.lacp.as_ref() {
            ret.insert("lacp", zvariant::Value::new(v));
        }
        if let Some(v) = self.trunks.as_ref() {
            let mut trunk_values = zvariant::Array::new(
                zvariant::Signature::from_str_unchecked("a{sv}"),
            );
            for range in v {
                trunk_values.append(range.to_value()?)?;
            }
            ret.insert("trunks", zvariant::Value::Array(trunk_values));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingOvsIface {
    pub iface_type: Option<String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingOvsIface {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            iface_type: _from_map!(v, "type", String::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingOvsIface {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.iface_type {
            ret.insert("type", zvariant::Value::new(v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingOvsExtIds {
    pub data: Option<HashMap<String, String>>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingOvsExtIds {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            data: _from_map!(v, "data", <HashMap<String, String>>::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingOvsExtIds {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.data {
            let mut dict_value = zvariant::Dict::new(
                zvariant::Signature::from_str_unchecked("s"),
                zvariant::Signature::from_str_unchecked("s"),
            );
            for (k, v) in v.iter() {
                dict_value
                    .append(zvariant::Value::new(k), zvariant::Value::new(v))?;
            }
            ret.insert("data", zvariant::Value::Dict(dict_value));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingOvsOtherConfig {
    pub data: Option<HashMap<String, String>>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingOvsOtherConfig {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            data: _from_map!(v, "data", <HashMap<String, String>>::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingOvsOtherConfig {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.data {
            let mut dict_value = zvariant::Dict::new(
                zvariant::Signature::from_str_unchecked("s"),
                zvariant::Signature::from_str_unchecked("s"),
            );
            for (k, v) in v.iter() {
                dict_value
                    .append(zvariant::Value::new(k), zvariant::Value::new(v))?;
            }
            ret.insert("data", zvariant::Value::Dict(dict_value));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingOvsPatch {
    pub peer: Option<String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingOvsPatch {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            peer: _from_map!(v, "peer", String::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingOvsPatch {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.peer {
            ret.insert("peer", zvariant::Value::new(v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingOvsDpdk {
    pub devargs: Option<String>,
    pub n_rxq: Option<u32>,
    pub n_rxq_desc: Option<u32>,
    pub n_txq_desc: Option<u32>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingOvsDpdk {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            devargs: _from_map!(v, "devargs", String::try_from)?,
            n_rxq: _from_map!(v, "n-rxq", u32::try_from)?,
            n_rxq_desc: _from_map!(v, "n-rxq-desc", u32::try_from)?,
            n_txq_desc: _from_map!(v, "n-txq-desc", u32::try_from)?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingOvsDpdk {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.devargs {
            ret.insert("devargs", zvariant::Value::new(v));
        }
        if let Some(v) = &self.n_rxq {
            ret.insert("n-rxq", zvariant::Value::new(v));
        }
        if let Some(v) = &self.n_rxq_desc {
            ret.insert("n-rxq-desc", zvariant::Value::new(v));
        }
        if let Some(v) = &self.n_txq_desc {
            ret.insert("n-txq-desc", zvariant::Value::new(v));
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}
