use std::collections::{HashMap, HashSet};
use std::convert::TryFrom;

use log::error;
use serde::Deserialize;

use super::super::{
    connection::DbusDictionary, ErrorKind, NmError, ToDbusValue,
};

#[derive(Debug, Clone, PartialEq, Default, Deserialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingVlan {
    pub parent: Option<String>,
    pub id: Option<u32>,
    pub protocol: Option<String>,
    pub flags: Vec<NmSettingVlanFlag>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NmSettingVlanFlag {
    ReorderHeaders = 1,
    Gvrp = 2,
    LooseBinding = 4,
    Mvrp = 8,
}

fn from_u32_to_vec_nm_vlan_flags(i: u32) -> Vec<NmSettingVlanFlag> {
    let mut ret = Vec::new();
    if i & NmSettingVlanFlag::ReorderHeaders as u32 > 0 {
        ret.push(NmSettingVlanFlag::ReorderHeaders);
    }
    if i & NmSettingVlanFlag::Gvrp as u32 > 0 {
        ret.push(NmSettingVlanFlag::Gvrp);
    }
    if i & NmSettingVlanFlag::LooseBinding as u32 > 0 {
        ret.push(NmSettingVlanFlag::LooseBinding);
    }
    if i & NmSettingVlanFlag::Mvrp as u32 > 0 {
        ret.push(NmSettingVlanFlag::Mvrp);
    }
    ret
}

fn from_vec_nm_vlan_flags_u32(flags: Vec<NmSettingVlanFlag>) -> u32 {
    let mut ret: u32 = 0;
    for flag in flags {
        ret |= flag as u32;
    }
    ret
}

fn from_dic_to_vec_nm_vlan_flags(
    v: &mut DbusDictionary,
    key: &str,
) -> Result<Vec<NmSettingVlanFlag>, NmError> {
    if let Some(flags) = v.remove(key) {
        Ok(from_u32_to_vec_nm_vlan_flags(u32::try_from(flags)?))
    } else {
        Ok(Vec::new())
    }
}

impl TryFrom<DbusDictionary> for NmSettingVlan {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            parent: _from_map!(v, "parent", String::try_from)?,
            id: _from_map!(v, "id", u32::try_from)?,
            protocol: _from_map!(v, "protocol", String::try_from)?,
            flags: from_dic_to_vec_nm_vlan_flags(&mut v, "flags")?,
            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingVlan {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value>, NmError> {
        let mut ret = HashMap::new();
        if let Some(v) = &self.parent {
            ret.insert("parent", zvariant::Value::new(v.clone()));
        }
        if let Some(id) = self.id {
            ret.insert("id", zvariant::Value::new(id));
        }
        if let Some(protocol) = self.protocol.as_ref() {
            ret.insert("protocol", zvariant::Value::new(protocol));
        }
        ret.insert(
            "flags",
            zvariant::Value::new(from_vec_nm_vlan_flags_u32(
                self.flags.clone(),
            )),
        );
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

const NM_VLAN_PROTOCOL_802_1Q: &str = "802.1Q";
const NM_VLAN_PROTOCOL_802_1AD: &str = "802.1ad";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
pub enum NmVlanProtocol {
    Dot1Q,
    Dot1Ad,
}

impl Default for NmVlanProtocol {
    fn default() -> Self {
        Self::Dot1Q
    }
}

impl From<crate::VlanProtocol> for NmVlanProtocol {
    fn from(proto: crate::VlanProtocol) -> Self {
        match proto {
            crate::VlanProtocol::Ieee8021Q => Self::Dot1Q,
            crate::VlanProtocol::Ieee8021Ad => Self::Dot1Ad,
        }
    }
}

impl TryFrom<String> for NmVlanProtocol {
    type Error = NmError;
    fn try_from(vlan_protocol: String) -> Result<Self, Self::Error> {
        match vlan_protocol.as_str() {
            NM_VLAN_PROTOCOL_802_1Q => Ok(Self::Dot1Q),
            NM_VLAN_PROTOCOL_802_1AD => Ok(Self::Dot1Ad),
            _ => {
                let e = NmError::new(
                    ErrorKind::InvalidArgument,
                    format!(
                        "Invalid VLAN protocol {vlan_protocol}, only support: {NM_VLAN_PROTOCOL_802_1Q} and {NM_VLAN_PROTOCOL_802_1AD}"
                    ),
                );
                error!("{}", e);
                Err(e)
            }
        }
    }
}

impl std::fmt::Display for NmVlanProtocol {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Dot1Q => NM_VLAN_PROTOCOL_802_1Q,
                Self::Dot1Ad => NM_VLAN_PROTOCOL_802_1AD,
            }
        )
    }
}
