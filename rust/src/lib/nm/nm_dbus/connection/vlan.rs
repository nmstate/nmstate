// SPDX-License-Identifier: Apache-2.0

use std::collections::{HashMap, HashSet};
use std::convert::TryFrom;

use log::error;
use serde::{Deserialize, Serialize};

use super::super::{
    connection::DbusDictionary, ErrorKind, NmError, ToDbusValue,
};

#[derive(Debug, Clone, PartialEq, Default, Deserialize, Serialize)]
#[serde(try_from = "DbusDictionary")]
#[non_exhaustive]
pub struct NmSettingVlan {
    pub parent: Option<String>,
    pub id: Option<u32>,
    pub protocol: Option<String>,
    pub flags: Vec<NmSettingVlanFlag>,
    pub egress_priority_map: Vec<String>,
    pub ingress_priority_map: Vec<String>,
    _other: HashMap<String, zvariant::OwnedValue>,
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
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
            egress_priority_map: _from_map!(
                v,
                "egress-priority-map",
                Vec::<String>::try_from
            )?
            .unwrap_or_default(),
            ingress_priority_map: _from_map!(
                v,
                "ingress-priority-map",
                Vec::<String>::try_from
            )?
            .unwrap_or_default(),

            _other: v,
        })
    }
}

impl ToDbusValue for NmSettingVlan {
    fn to_value(&self) -> Result<HashMap<&str, zvariant::Value<'_>>, NmError> {
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

        ret.insert(
            "egress-priority-map",
            zvariant::Value::new(self.egress_priority_map.as_slice()),
        );
        ret.insert(
            "ingress-priority-map",
            zvariant::Value::new(self.ingress_priority_map.as_slice()),
        );
        ret.extend(self._other.iter().map(|(key, value)| {
            (key.as_str(), zvariant::Value::from(value.clone()))
        }));
        Ok(ret)
    }
}

const NM_VLAN_PROTOCOL_802_1Q: &str = "802.1Q";
const NM_VLAN_PROTOCOL_802_1AD: &str = "802.1ad";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[non_exhaustive]
#[derive(Default)]
pub enum NmVlanProtocol {
    #[default]
    Dot1Q,
    Dot1Ad,
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
                        "Invalid VLAN protocol {vlan_protocol}, only support: \
                         {NM_VLAN_PROTOCOL_802_1Q} and \
                         {NM_VLAN_PROTOCOL_802_1AD}"
                    ),
                );
                error!("{e}");
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
