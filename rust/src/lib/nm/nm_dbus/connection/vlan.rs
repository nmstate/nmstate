use std::collections::HashMap;
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
    _other: HashMap<String, zvariant::OwnedValue>,
}

impl TryFrom<DbusDictionary> for NmSettingVlan {
    type Error = NmError;
    fn try_from(mut v: DbusDictionary) -> Result<Self, Self::Error> {
        Ok(Self {
            parent: _from_map!(v, "parent", String::try_from)?,
            id: _from_map!(v, "id", u32::try_from)?,
            protocol: _from_map!(v, "protocol", String::try_from)?,
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
