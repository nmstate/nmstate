// SPDX-License-Identifier: Apache-2.0

use serde::{de::IgnoredAny, Deserialize, Deserializer, Serialize};

const LLDP_SYS_CAP_OTHER: u16 = 1;
const LLDP_SYS_CAP_REPEATER: u16 = 2;
const LLDP_SYS_CAP_MAC_BRIDGE: u16 = 3;
const LLDP_SYS_CAP_AP: u16 = 4;
const LLDP_SYS_CAP_ROUTER: u16 = 5;
const LLDP_SYS_CAP_TELEPHONE: u16 = 6;
const LLDP_SYS_CAP_DOCSIS: u16 = 7;
const LLDP_SYS_CAP_STATION_ONLY: u16 = 8;
const LLDP_SYS_CAP_CVLAN: u16 = 9;
const LLDP_SYS_CAP_SVLAN: u16 = 10;
const LLDP_SYS_CAP_TWO_PORT_MAC_RELAY: u16 = 11;

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[repr(u8)]
#[serde(into = "u8")]
pub enum LldpNeighborTlvType {
    ChassisId = 1,
    Port = 2,
    SystemName = 5,
    SystemDescription = 6,
    SystemCapabilities = 7,
    ManagementAddress = 8,
    OrganizationSpecific = 127,
}

impl From<LldpNeighborTlvType> for u8 {
    fn from(value: LldpNeighborTlvType) -> Self {
        value as Self
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[repr(u8)]
#[serde(into = "u8")]
pub enum LldpOrgSubtype {
    Vlan = 3,
    MacPhyConf = 1,
    Ppvids = 2,
    MaxFrameSize = 4,
}

impl From<LldpOrgSubtype> for u8 {
    fn from(value: LldpOrgSubtype) -> Self {
        value as Self
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub enum LldpOrgOiu {
    #[serde(rename = "00:80:c2")]
    Vlan,
    #[serde(rename = "00:12:0f")]
    MacPhyConf,
    #[serde(rename = "00:80:c2")]
    Ppvids,
    #[serde(rename = "00:12:0f")]
    MaxFrameSize,
}

#[derive(Debug, Clone, PartialEq, Eq, Default, Deserialize, Serialize)]
#[non_exhaustive]
#[serde(deny_unknown_fields)]
pub struct LldpConfig {
    #[serde(deserialize_with = "crate::deserializer::bool_or_string")]
    pub enabled: bool,
    #[serde(
        default,
        deserialize_with = "skip",
        skip_serializing_if = "Vec::is_empty"
    )]
    pub neighbors: Vec<Vec<LldpNeighborTlv>>,
}

// The serde is treating skipped value as unknown field which trigger
// `serde(deny_unknown_fields)`, so we manually skip this field.
fn skip<'de, D, T>(deserializer: D) -> Result<T, D::Error>
where
    D: Deserializer<'de>,
    T: Default,
{
    // Ignore the data in the input.
    IgnoredAny::deserialize(deserializer)?;
    Ok(T::default())
}

impl LldpConfig {
    pub(crate) fn sanitize(&mut self) {
        // Remove since it is for query only
        self.neighbors = Vec::new();
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(untagged)]
#[non_exhaustive]
pub enum LldpNeighborTlv {
    SystemName(LldpSystemName),
    SystemDescription(LldpSystemDescription),
    SystemCapabilities(LldpSystemCapabilities),
    ChassisId(LldpChassisId),
    PortId(LldpPortId),
    Ieee8021Vlans(LldpVlans),
    Ieee8023MacPhyConf(LldpMacPhy),
    Ieee8021Ppvids(LldpPpvids),
    ManagementAddresses(LldpMgmtAddrs),
    Ieee8023MaxFrameSize(LldpMaxFrameSize),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct LldpSystemName {
    #[serde(rename = "type")]
    pub ty: LldpNeighborTlvType,
    pub system_name: String,
}

impl LldpSystemName {
    pub fn new(value: String) -> Self {
        Self {
            system_name: value,
            ty: LldpNeighborTlvType::SystemName,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct LldpSystemDescription {
    #[serde(rename = "type")]
    pub ty: LldpNeighborTlvType,
    pub system_description: String,
}

impl LldpSystemDescription {
    pub fn new(value: String) -> Self {
        Self {
            system_description: value,
            ty: LldpNeighborTlvType::SystemDescription,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct LldpChassisId {
    #[serde(rename = "type")]
    pub ty: LldpNeighborTlvType,
    pub chassis_id: String,
    pub chassis_id_type: LldpChassisIdType,
    #[serde(rename = "_description")]
    pub description: String,
}

impl LldpChassisId {
    pub fn new(chassis_id: String, chassis_id_type: LldpChassisIdType) -> Self {
        Self {
            chassis_id,
            chassis_id_type: chassis_id_type.clone(),
            description: chassis_id_type.into(),
            ty: LldpNeighborTlvType::ChassisId,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[repr(u8)]
#[serde(into = "u8")]
pub enum LldpChassisIdType {
    Reserved = 0,
    ChassisComponent = 1,
    InterfaceAlias = 2,
    PortComponent = 3,
    MacAddress = 4,
    NetworkAddress = 5,
    InterfaceName = 6,
    LocallyAssigned = 7,
}

impl From<LldpChassisIdType> for u8 {
    fn from(value: LldpChassisIdType) -> Self {
        value as Self
    }
}

impl From<u8> for LldpChassisIdType {
    fn from(v: u8) -> LldpChassisIdType {
        if v == LldpChassisIdType::ChassisComponent as u8 {
            LldpChassisIdType::ChassisComponent
        } else if v == LldpChassisIdType::InterfaceAlias as u8 {
            LldpChassisIdType::InterfaceAlias
        } else if v == LldpChassisIdType::PortComponent as u8 {
            LldpChassisIdType::PortComponent
        } else if v == LldpChassisIdType::MacAddress as u8 {
            LldpChassisIdType::MacAddress
        } else if v == LldpChassisIdType::NetworkAddress as u8 {
            LldpChassisIdType::NetworkAddress
        } else if v == LldpChassisIdType::InterfaceName as u8 {
            LldpChassisIdType::InterfaceName
        } else if v == LldpChassisIdType::LocallyAssigned as u8 {
            LldpChassisIdType::LocallyAssigned
        } else {
            LldpChassisIdType::Reserved
        }
    }
}

impl From<LldpChassisIdType> for String {
    fn from(v: LldpChassisIdType) -> String {
        match v {
            LldpChassisIdType::Reserved => "Reserved",
            LldpChassisIdType::ChassisComponent => "Chasis compontent",
            LldpChassisIdType::InterfaceAlias => "Interface alias",
            LldpChassisIdType::PortComponent => "Port component",
            LldpChassisIdType::MacAddress => "MAC address",
            LldpChassisIdType::NetworkAddress => "Network address",
            LldpChassisIdType::InterfaceName => "Interface name",
            LldpChassisIdType::LocallyAssigned => "Locally assigned",
        }
        .to_string()
    }
}

impl Default for LldpChassisIdType {
    fn default() -> Self {
        Self::Reserved
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct LldpSystemCapabilities {
    #[serde(rename = "type")]
    pub ty: LldpNeighborTlvType,
    pub system_capabilities: Vec<LldpSystemCapability>,
}

impl LldpSystemCapabilities {
    pub fn new(system_capabilities: Vec<LldpSystemCapability>) -> Self {
        Self {
            system_capabilities,
            ty: LldpNeighborTlvType::SystemCapabilities,
        }
    }
}

impl From<u16> for LldpSystemCapabilities {
    fn from(caps: u16) -> Self {
        let mut ret = Vec::new();
        if (caps & 1 << (LLDP_SYS_CAP_OTHER - 1)) > 0 {
            ret.push(LldpSystemCapability::Other);
        }
        if (caps & 1 << (LLDP_SYS_CAP_REPEATER - 1)) > 0 {
            ret.push(LldpSystemCapability::Repeater);
        }
        if (caps & 1 << (LLDP_SYS_CAP_MAC_BRIDGE - 1)) > 0 {
            ret.push(LldpSystemCapability::MacBridgeComponent);
        }
        if (caps & 1 << (LLDP_SYS_CAP_AP - 1)) > 0 {
            ret.push(LldpSystemCapability::AccessPoint);
        }
        if (caps & 1 << (LLDP_SYS_CAP_ROUTER - 1)) > 0 {
            ret.push(LldpSystemCapability::Router);
        }
        if (caps & 1 << (LLDP_SYS_CAP_TELEPHONE - 1)) > 0 {
            ret.push(LldpSystemCapability::Telephone);
        }
        if (caps & 1 << (LLDP_SYS_CAP_DOCSIS - 1)) > 0 {
            ret.push(LldpSystemCapability::DocsisCableDevice);
        }
        if (caps & 1 << (LLDP_SYS_CAP_STATION_ONLY - 1)) > 0 {
            ret.push(LldpSystemCapability::StationOnly);
        }
        if (caps & 1 << (LLDP_SYS_CAP_CVLAN - 1)) > 0 {
            ret.push(LldpSystemCapability::CVlanComponent);
        }
        if (caps & 1 << (LLDP_SYS_CAP_SVLAN - 1)) > 0 {
            ret.push(LldpSystemCapability::SVlanComponent);
        }
        if (caps & 1 << (LLDP_SYS_CAP_TWO_PORT_MAC_RELAY - 1)) > 0 {
            ret.push(LldpSystemCapability::TwoPortMacRelayComponent);
        }
        Self::new(ret)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
pub enum LldpSystemCapability {
    Other,
    Repeater,
    #[serde(rename = "MAC Bridge component")]
    MacBridgeComponent,
    #[serde(rename = "802.11 Access Point (AP)")]
    AccessPoint,
    Router,
    Telephone,
    #[serde(rename = "DOCSIS cable device")]
    DocsisCableDevice,
    #[serde(rename = "Station Only")]
    StationOnly,
    #[serde(rename = "C-VLAN component")]
    CVlanComponent,
    #[serde(rename = "S-VLAN component")]
    SVlanComponent,
    #[serde(rename = "Two-port MAC Relay component")]
    TwoPortMacRelayComponent,
}

impl Default for LldpSystemCapability {
    fn default() -> Self {
        Self::Other
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct LldpPortId {
    #[serde(rename = "type")]
    pub ty: LldpNeighborTlvType,
    pub port_id: String,
    pub port_id_type: LldpPortIdType,
    #[serde(rename = "_description")]
    pub description: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[repr(u8)]
#[serde(into = "u8")]
pub enum LldpPortIdType {
    Reserved = 0,
    InterfaceAlias = 1,
    PortComponent = 2,
    MacAddress = 3,
    NetworkAddress = 4,
    InterfaceName = 5,
    AgentCircuitId = 6,
    LocallyAssigned = 7,
}

impl From<LldpPortIdType> for u8 {
    fn from(value: LldpPortIdType) -> Self {
        value as Self
    }
}

impl From<LldpPortIdType> for String {
    fn from(v: LldpPortIdType) -> String {
        match v {
            LldpPortIdType::Reserved => "Reserved",
            LldpPortIdType::InterfaceAlias => "Interface alias",
            LldpPortIdType::PortComponent => "Port component",
            LldpPortIdType::MacAddress => "MAC address",
            LldpPortIdType::NetworkAddress => "Network address",
            LldpPortIdType::InterfaceName => "Interface name",
            LldpPortIdType::AgentCircuitId => "Agent circuit ID",
            LldpPortIdType::LocallyAssigned => "Locally assigned",
        }
        .to_string()
    }
}

impl From<u8> for LldpPortIdType {
    fn from(v: u8) -> LldpPortIdType {
        if v == LldpPortIdType::InterfaceName as u8 {
            LldpPortIdType::InterfaceName
        } else if v == LldpPortIdType::PortComponent as u8 {
            LldpPortIdType::PortComponent
        } else if v == LldpPortIdType::MacAddress as u8 {
            LldpPortIdType::MacAddress
        } else if v == LldpPortIdType::NetworkAddress as u8 {
            LldpPortIdType::NetworkAddress
        } else if v == LldpPortIdType::AgentCircuitId as u8 {
            LldpPortIdType::AgentCircuitId
        } else if v == LldpPortIdType::LocallyAssigned as u8 {
            LldpPortIdType::LocallyAssigned
        } else {
            LldpPortIdType::Reserved
        }
    }
}

impl LldpPortId {
    pub fn new(port_id: String, port_id_type: LldpPortIdType) -> Self {
        Self {
            port_id,
            port_id_type: port_id_type.clone(),
            description: port_id_type.into(),
            ty: LldpNeighborTlvType::Port,
        }
    }
}

impl Default for LldpPortIdType {
    fn default() -> Self {
        Self::Reserved
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct LldpVlans {
    #[serde(rename = "type")]
    pub ty: LldpNeighborTlvType,
    pub ieee_802_1_vlans: Vec<LldpVlan>,
    pub oui: LldpOrgOiu,
    pub subtype: LldpOrgSubtype,
}

impl LldpVlans {
    pub fn new(ieee_802_1_vlans: Vec<LldpVlan>) -> Self {
        Self {
            ieee_802_1_vlans,
            oui: LldpOrgOiu::Vlan,
            subtype: LldpOrgSubtype::Vlan,
            ty: LldpNeighborTlvType::OrganizationSpecific,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Default)]
#[non_exhaustive]
pub struct LldpVlan {
    pub name: String,
    pub vid: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case")]
pub struct LldpMacPhy {
    #[serde(rename = "type")]
    pub ty: LldpNeighborTlvType,
    pub ieee_802_3_mac_phy_conf: LldpMacPhyConf,
    pub oui: LldpOrgOiu,
    pub subtype: LldpOrgSubtype,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case")]
pub struct LldpMacPhyConf {
    pub autoneg: bool,
    pub operational_mau_type: u16,
    pub pmd_autoneg_cap: u16,
}

impl LldpMacPhy {
    pub fn new(
        autoneg: bool,
        operational_mau_type: u16,
        pmd_autoneg_cap: u16,
    ) -> Self {
        Self {
            ieee_802_3_mac_phy_conf: LldpMacPhyConf {
                autoneg,
                operational_mau_type,
                pmd_autoneg_cap,
            },
            oui: LldpOrgOiu::MacPhyConf,
            subtype: LldpOrgSubtype::MacPhyConf,
            ty: LldpNeighborTlvType::OrganizationSpecific,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct LldpPpvids {
    #[serde(rename = "type")]
    pub ty: LldpNeighborTlvType,
    pub ieee_802_1_ppvids: Vec<u32>,
    pub oui: LldpOrgOiu,
    pub subtype: LldpOrgSubtype,
}

impl LldpPpvids {
    pub fn new(ieee_802_1_ppvids: Vec<u32>) -> Self {
        Self {
            ieee_802_1_ppvids,
            oui: LldpOrgOiu::Ppvids,
            subtype: LldpOrgSubtype::Ppvids,
            ty: LldpNeighborTlvType::OrganizationSpecific,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case")]
pub struct LldpMgmtAddrs {
    #[serde(rename = "type")]
    pub ty: LldpNeighborTlvType,
    pub management_addresses: Vec<LldpMgmtAddr>,
}

impl LldpMgmtAddrs {
    pub fn new(management_addresses: Vec<LldpMgmtAddr>) -> Self {
        Self {
            management_addresses,
            ty: LldpNeighborTlvType::ManagementAddress,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Default)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case")]
pub struct LldpMgmtAddr {
    pub address: String,
    pub address_subtype: LldpAddressFamily,
    pub interface_number: u32,
    pub interface_number_subtype: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
pub enum LldpAddressFamily {
    Unknown,
    #[serde(rename = "IPv4")]
    Ipv4,
    #[serde(rename = "IPv6")]
    Ipv6,
    #[serde(rename = "MAC")]
    Mac,
}

impl Default for LldpAddressFamily {
    fn default() -> Self {
        Self::Unknown
    }
}

const ADDRESS_FAMILY_IP4: u16 = 1;
const ADDRESS_FAMILY_IP6: u16 = 2;
const ADDRESS_FAMILY_MAC: u16 = 6;

impl From<u16> for LldpAddressFamily {
    fn from(i: u16) -> Self {
        match i {
            ADDRESS_FAMILY_IP4 => Self::Ipv4,
            ADDRESS_FAMILY_IP6 => Self::Ipv6,
            ADDRESS_FAMILY_MAC => Self::Mac,
            _ => Self::Unknown,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
pub struct LldpMaxFrameSize {
    #[serde(rename = "type")]
    pub ty: LldpNeighborTlvType,
    pub ieee_802_3_max_frame_size: u32,
    pub oui: LldpOrgOiu,
    pub subtype: LldpOrgSubtype,
}

impl LldpMaxFrameSize {
    pub fn new(ieee_802_3_max_frame_size: u32) -> Self {
        Self {
            ieee_802_3_max_frame_size,
            oui: LldpOrgOiu::MaxFrameSize,
            subtype: LldpOrgSubtype::MaxFrameSize,
            ty: LldpNeighborTlvType::OrganizationSpecific,
        }
    }
}
