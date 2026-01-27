// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::{
    ifaces::Ip6TunnelFlag,
    nm::nm_dbus::{NmError, ToDbusValue, connection::DbusDictionary},
};

#[derive(Debug, Clone, PartialEq, Default, Deserialize, Serialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingIpTunnel {
    pub mode: Option<u32>,
    pub parent: Option<String>,
    pub local: Option<String>,
    pub remote: Option<String>,
    pub ttl: Option<u32>,
    pub tos: Option<u32>,
    pub path_mtu_discovery: Option<bool>,
    pub input_key: Option<String>,
    pub output_key: Option<String>,
    pub encap_limit: Option<u32>,
    pub flow_label: Option<u32>,
    pub fwmark: Option<u32>,
    pub flags: Vec<NmSettingIpTunnelFlag>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
pub enum NmSettingIpTunnelFlag {
    Other = 0x0,
    IgnEncapLimit = 0x1,
    UseOrigTclass = 0x2,
    UseOrigFlowlabel = 0x4,
    Mip6Dev = 0x8,
    RcvDscpCopy = 0x10,
    UseOrigFwMark = 0x20,
    AllowLocalRemote = 0x40,
}

impl From<Ip6TunnelFlag> for NmSettingIpTunnelFlag {
    fn from(flag: Ip6TunnelFlag) -> Self {
        match flag {
            Ip6TunnelFlag::IgnEncapLimit => {
                NmSettingIpTunnelFlag::IgnEncapLimit
            }
            Ip6TunnelFlag::UseOrigTclass => {
                NmSettingIpTunnelFlag::UseOrigTclass
            }
            Ip6TunnelFlag::UseOrigFlowlabel => {
                NmSettingIpTunnelFlag::UseOrigFlowlabel
            }
            Ip6TunnelFlag::Mip6Dev => NmSettingIpTunnelFlag::Mip6Dev,
            Ip6TunnelFlag::RcvDscpCopy => NmSettingIpTunnelFlag::RcvDscpCopy,
            Ip6TunnelFlag::UseOrigFwMark => {
                NmSettingIpTunnelFlag::UseOrigFwMark
            }
            Ip6TunnelFlag::AllowLocalRemote => {
                NmSettingIpTunnelFlag::AllowLocalRemote
            }
            _ => NmSettingIpTunnelFlag::Other,
        }
    }
}

fn from_u32_to_vec_nm_ip_tunnel_flags(i: u32) -> Vec<NmSettingIpTunnelFlag> {
    let mut ret = Vec::new();
    if i & NmSettingIpTunnelFlag::IgnEncapLimit as u32 > 0 {
        ret.push(NmSettingIpTunnelFlag::IgnEncapLimit);
    }
    if i & NmSettingIpTunnelFlag::UseOrigTclass as u32 > 0 {
        ret.push(NmSettingIpTunnelFlag::UseOrigTclass);
    }
    if i & NmSettingIpTunnelFlag::UseOrigFlowlabel as u32 > 0 {
        ret.push(NmSettingIpTunnelFlag::UseOrigFlowlabel);
    }
    if i & NmSettingIpTunnelFlag::Mip6Dev as u32 > 0 {
        ret.push(NmSettingIpTunnelFlag::Mip6Dev);
    }
    if i & NmSettingIpTunnelFlag::RcvDscpCopy as u32 > 0 {
        ret.push(NmSettingIpTunnelFlag::RcvDscpCopy);
    }
    if i & NmSettingIpTunnelFlag::UseOrigFwMark as u32 > 0 {
        ret.push(NmSettingIpTunnelFlag::UseOrigFwMark);
    }
    if i & NmSettingIpTunnelFlag::AllowLocalRemote as u32 > 0 {
        ret.push(NmSettingIpTunnelFlag::AllowLocalRemote);
    }
    ret
}

fn from_vec_nm_ip_tunnel_flags_u32(flags: &[NmSettingIpTunnelFlag]) -> u32 {
    let mut ret: u32 = 0;
    for flag in flags.iter() {
        ret |= flag.clone() as u32;
    }
    ret
}

fn from_dic_to_vec_nm_ip_tunnel_flags(
    v: &mut DbusDictionary,
    key: &str,
) -> Result<Vec<NmSettingIpTunnelFlag>, NmError> {
    if let Some(flags) = v.remove(key) {
        Ok(from_u32_to_vec_nm_ip_tunnel_flags(u32::try_from(flags)?))
    } else {
        Ok(Vec::new())
    }
}

impl TryFrom<DbusDictionary> for NmSettingIpTunnel {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            mode: _from_map!(v, "mode", u32::try_from)?,
            parent: _from_map!(v, "parent", String::try_from)?,
            local: _from_map!(v, "local", String::try_from)?,
            remote: _from_map!(v, "remote", String::try_from)?,
            ttl: _from_map!(v, "ttl", u32::try_from)?,
            tos: _from_map!(v, "tos", u32::try_from)?,
            path_mtu_discovery: _from_map!(
                v,
                "path-mtu-discovery",
                bool::try_from
            )?,
            input_key: _from_map!(v, "input-key", String::try_from)?,
            output_key: _from_map!(v, "output-key", String::try_from)?,
            encap_limit: _from_map!(v, "encapsulation-limit", u32::try_from)?,
            flow_label: _from_map!(v, "flow-label", u32::try_from)?,
            fwmark: _from_map!(v, "fwmark", u32::try_from)?,
            flags: from_dic_to_vec_nm_ip_tunnel_flags(&mut v, "flags")?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingIpTunnel {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value<'_>>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.mode {
            ret.insert("mode", zvariant::Value::new(v));
        }
        if let Some(v) = &self.parent {
            ret.insert("parent", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.local {
            ret.insert("local", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.remote {
            ret.insert("remote", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.ttl {
            ret.insert("ttl", zvariant::Value::new(v));
        }
        if let Some(v) = &self.tos {
            ret.insert("tos", zvariant::Value::new(v));
        }
        if let Some(v) = &self.path_mtu_discovery {
            ret.insert("path-mtu-discovery", zvariant::Value::new(v));
        }
        if let Some(v) = &self.input_key {
            ret.insert("input-key", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.output_key {
            ret.insert("output-key", zvariant::Value::new(v.clone()));
        }
        if let Some(v) = &self.encap_limit {
            ret.insert("encapsulation-limit", zvariant::Value::new(v));
        }
        if let Some(v) = &self.flow_label {
            ret.insert("flow-label", zvariant::Value::new(v));
        }
        if let Some(v) = &self.fwmark {
            ret.insert("fwmark", zvariant::Value::new(v));
        }
        if !self.flags.is_empty() {
            ret.insert(
                "flags",
                zvariant::Value::new(from_vec_nm_ip_tunnel_flags_u32(
                    &self.flags,
                )),
            );
        }
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}
