// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use serde::{Deserialize, Deserializer, Serialize};
use serde::de::Visitor;
use std::fmt;
use serde::de;

use crate::{
    BaseInterface, BondInterface, DummyInterface, ErrorKind, EthernetInterface,
    HsrInterface, InfiniBandInterface, IpsecInterface, LinuxBridgeInterface,
    LoopbackInterface, MacSecInterface, MacVlanInterface, MacVtapInterface,
    NmstateError, OvsBridgeInterface, OvsInterface, VlanInterface,
    VrfInterface, VxlanInterface, XfrmInterface,
};

use crate::state::merge_json_value;

#[derive(
    Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize,
)]
#[non_exhaustive]
#[serde(rename_all = "kebab-case")]
/// Interface type
pub enum InterfaceType {
    /// [Bond interface](https://www.kernel.org/doc/Documentation/networking/bonding.txt)
    /// Deserialize and serialize from/to 'bond'
    Bond,
    /// Bridge provided by Linux kernel.
    /// Deserialize and serialize from/to 'linux-bridge'.
    LinuxBridge,
    /// Dummy interface.
    /// Deserialize and serialize from/to 'dummy'.
    Dummy,
    /// Ethernet interface.
    /// Deserialize and serialize from/to 'ethernet'.
    Ethernet,
    /// HSR interface.
    /// Deserialize and serialize from/to 'hsr'.
    Hsr,
    /// Loopback interface.
    /// Deserialize and serialize from/to 'loopback'.
    Loopback,
    /// MAC VLAN interface.
    /// Deserialize and serialize from/to 'mac-vlan'.
    MacVlan,
    /// MAC VTAP interface.
    /// Deserialize and serialize from/to 'mac-vtap'.
    MacVtap,
    /// OpenvSwitch bridge.
    /// Deserialize and serialize from/to 'ovs-bridge'.
    OvsBridge,
    /// OpenvSwitch system interface.
    /// Deserialize and serialize from/to 'ovs-interface'.
    OvsInterface,
    /// Virtual ethernet provide by Linux kernel.
    /// Deserialize and serialize from/to 'veth'.
    Veth,
    /// VLAN interface.
    /// Deserialize and serialize from/to 'vlan'.
    Vlan,
    /// [Virtual Routing and Forwarding interface](https://www.kernel.org/doc/html/latest/networking/vrf.html)
    /// Deserialize and serialize from/to 'vrf'.
    Vrf,
    /// VxVLAN interface.
    /// Deserialize and serialize from/to 'vxlan'.
    Vxlan,
    /// [IP over InfiniBand interface](https://docs.kernel.org/infiniband/ipoib.html)
    /// Deserialize and serialize from/to 'infiniband'.
    #[serde(rename = "infiniband")]
    InfiniBand,
    /// TUN interface. Only used for query, will be ignored when applying.
    /// Deserialize and serialize from/to 'tun'.
    Tun,
    /// MACsec interface.
    /// Deserialize and serialize from/to 'macsec'
    #[serde(rename = "macsec")]
    MacSec,
    /// Ipsec connection.
    Ipsec,
    /// Linux Xfrm kernel interface
    Xfrm,
    /// Unknown interface.
    Unknown,
    /// Reserved for future use.
    #[serde(untagged)]
    Other(String),
}

impl Default for InterfaceType {
    fn default() -> Self {
        Self::Unknown
    }
}

//NOTE: Remember to add new interface types also here
impl std::fmt::Display for InterfaceType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                InterfaceType::Bond => "bond",
                InterfaceType::LinuxBridge => "linux-bridge",
                InterfaceType::Dummy => "dummy",
                InterfaceType::Ethernet => "ethernet",
                InterfaceType::Hsr => "hsr",
                InterfaceType::Loopback => "loopback",
                InterfaceType::MacVlan => "mac-vlan",
                InterfaceType::MacVtap => "mac-vtap",
                InterfaceType::OvsBridge => "ovs-bridge",
                InterfaceType::OvsInterface => "ovs-interface",
                InterfaceType::Veth => "veth",
                InterfaceType::Vlan => "vlan",
                InterfaceType::Vrf => "vrf",
                InterfaceType::Vxlan => "vxlan",
                InterfaceType::InfiniBand => "infiniband",
                InterfaceType::Unknown => "unknown",
                InterfaceType::Tun => "tun",
                InterfaceType::MacSec => "macsec",
                InterfaceType::Ipsec => "ipsec",
                InterfaceType::Xfrm => "xfrm",
                InterfaceType::Other(ref s) => s,
            }
        )
    }
}

impl InterfaceType {
    const USERSPACE_IFACE_TYPES: [Self; 2] = [Self::OvsBridge, Self::Ipsec];
    const CONTROLLER_IFACES_TYPES: [Self; 4] =
        [Self::Bond, Self::LinuxBridge, Self::OvsBridge, Self::Vrf];

    // other interfaces are also considered as userspace
    pub(crate) fn is_userspace(&self) -> bool {
        self.is_other() || Self::USERSPACE_IFACE_TYPES.contains(self)
    }

    pub(crate) fn is_other(&self) -> bool {
        matches!(self, Self::Other(_))
    }

    pub(crate) fn is_controller(&self) -> bool {
        Self::CONTROLLER_IFACES_TYPES.contains(self)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
/// The state of interface
pub enum InterfaceState {
    /// Interface is up and running.
    /// Deserialize and serialize from/to 'up'.
    Up,
    /// For apply action, down means configuration still exist but
    /// deactivate. The virtual interface will be removed and other interface
    /// will be reverted to down state or up with IP disabled state.
    /// Deserialize and serialize from/to 'down'.
    Down,
    /// Only for apply action to remove configuration and deactivate the
    /// interface.
    Absent,
    /// Unknown state.
    Unknown,
    /// Interface is not managed by backend. For apply action, interface marked
    /// as ignore will not be changed and will not cause verification failure
    /// neither.
    /// When desired controller listed currently ignored interfaces as its
    /// port, nmstate will automatically convert these ignored interfaces from
    /// 'state: ignore' to 'state: up' only when:
    ///  1. This ignored port is not mentioned in desire state.
    ///  2. This ignored port is listed as port of a desired controller.
    ///  3. Controller interface is new or does not contain ignored interfaces
    ///     currently.
    ///
    /// Deserialize and serialize from/to 'ignore'.
    Ignore,
}

impl Default for InterfaceState {
    fn default() -> Self {
        Self::Up
    }
}

impl From<&str> for InterfaceState {
    fn from(s: &str) -> Self {
        match s {
            "up" => Self::Up,
            "down" => Self::Down,
            "absent" => Self::Absent,
            "ignore" => Self::Ignore,
            _ => Self::Unknown,
        }
    }
}

impl<'de> Deserialize<'de> for InterfaceState {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        struct InterfaceStateVisitor;

        impl<'de> Visitor<'de> for InterfaceStateVisitor{
            type Value = InterfaceState;

            fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result{
                formatter.write_str("a string for an interface state")
            }

            fn visit_str<E>(self, value: &str) -> Result<InterfaceState, E>
            where 
                E: de::Error,
            {

                match value {
                    "up" => Ok(InterfaceState::Up),
                    "down" => Ok(InterfaceState::Down),
                    "absent" => Ok(InterfaceState::Absent),
                    "ignore" => Ok(InterfaceState::Ignore),
                    "unknown" => {
                        log::warn!("Interface state is 'unknown'; it will be ignored.");
                        Ok(InterfaceState::Ignore)
                    },
                    _ => Err(E::custom(format!("unexpected interface state: {}", value))),
                }
                
            }
        }
        deserializer.deserialize_str(InterfaceStateVisitor)
    }  

}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Default)]
#[non_exhaustive]
/// Holder for interface with known interface type defined.
/// During apply action, nmstate can resolve unknown interface to first
/// found interface type.
pub struct UnknownInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
    #[serde(flatten)]
    pub(crate) other: serde_json::Value,
}

impl UnknownInterface {
    pub fn new() -> Self {
        Self::default()
    }
}

impl<'de> Deserialize<'de> for UnknownInterface {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let mut ret = UnknownInterface::default();
        let mut v = serde_json::Map::deserialize(deserializer)?;
        let mut base_value = serde_json::map::Map::new();
        if let Some(n) = v.remove("name") {
            base_value.insert("name".to_string(), n);
        }
        if let Some(s) = v.remove("state") {
            base_value.insert("state".to_string(), s);
        }
        // The BaseInterface will only have name and state
        // These two properties are also stored in `other` for serializing
        ret.base = BaseInterface::deserialize(
            serde_json::value::Value::Object(base_value),
        )
        .map_err(serde::de::Error::custom)?;
        ret.other = serde_json::Value::Object(v);
        Ok(ret)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case", untagged)]
#[non_exhaustive]
/// Represent a kernel or user space network interface.
pub enum Interface {
    /// [Bond interface](https://www.kernel.org/doc/Documentation/networking/bonding.txt)
    Bond(BondInterface),
    /// Dummy interface.
    Dummy(DummyInterface),
    /// Ethernet interface or virtual ethernet(veth) of linux kernel
    Ethernet(EthernetInterface),
    /// HSR interface provided by Linux kernel.
    Hsr(HsrInterface),
    /// Bridge provided by Linux kernel.
    LinuxBridge(LinuxBridgeInterface),
    /// OpenvSwitch bridge.
    OvsBridge(OvsBridgeInterface),
    /// OpenvSwitch system interface.
    OvsInterface(OvsInterface),
    /// Unknown interface.
    Unknown(UnknownInterface),
    /// VLAN interface.
    Vlan(VlanInterface),
    /// VxLAN interface.
    Vxlan(VxlanInterface),
    /// MAC VLAN interface.
    MacVlan(MacVlanInterface),
    /// MAC VTAP interface.
    MacVtap(MacVtapInterface),
    /// [Virtual Routing and Forwarding interface](https://www.kernel.org/doc/html/latest/networking/vrf.html)
    Vrf(VrfInterface),
    /// [IP over InfiniBand interface](https://docs.kernel.org/infiniband/ipoib.html)
    InfiniBand(InfiniBandInterface),
    /// Linux loopback interface
    Loopback(LoopbackInterface),
    /// MACsec interface.
    MacSec(MacSecInterface),
    /// Ipsec connection
    Ipsec(IpsecInterface),
    /// Linux xfrm interface
    Xfrm(XfrmInterface),
}

impl<'de> Deserialize<'de> for Interface {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let mut v = serde_json::Value::deserialize(deserializer)?;

        // Ignore all properties except type if state: absent
        if matches!(
            Option::deserialize(&v["state"])
                .map_err(serde::de::Error::custom)?,
            Some(InterfaceState::Absent)
        ) {
            let mut new_value = serde_json::map::Map::new();
            if let Some(n) = v.get("name") {
                new_value.insert("name".to_string(), n.clone());
            }
            if let Some(t) = v.get("type") {
                new_value.insert("type".to_string(), t.clone());
            }
            if let Some(s) = v.get("state") {
                new_value.insert("state".to_string(), s.clone());
            }
            v = serde_json::value::Value::Object(new_value);
        }

        match Option::deserialize(&v["type"])
            .map_err(serde::de::Error::custom)?
        {
            Some(InterfaceType::Ethernet) => {
                let inner = EthernetInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Ethernet(inner))
            }
            Some(InterfaceType::LinuxBridge) => {
                let inner = LinuxBridgeInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::LinuxBridge(inner))
            }
            Some(InterfaceType::Bond) => {
                let inner = BondInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Bond(inner))
            }
            Some(InterfaceType::Veth) => {
                let inner = EthernetInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Ethernet(inner))
            }
            Some(InterfaceType::Vlan) => {
                let inner = VlanInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Vlan(inner))
            }
            Some(InterfaceType::Vxlan) => {
                let inner = VxlanInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Vxlan(inner))
            }
            Some(InterfaceType::Dummy) => {
                let inner = DummyInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Dummy(inner))
            }
            Some(InterfaceType::OvsInterface) => {
                let inner = OvsInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::OvsInterface(inner))
            }
            Some(InterfaceType::OvsBridge) => {
                let inner = OvsBridgeInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::OvsBridge(inner))
            }
            Some(InterfaceType::MacVlan) => {
                let inner = MacVlanInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::MacVlan(inner))
            }
            Some(InterfaceType::MacVtap) => {
                let inner = MacVtapInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::MacVtap(inner))
            }
            Some(InterfaceType::Vrf) => {
                let inner = VrfInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Vrf(inner))
            }
            Some(InterfaceType::Hsr) => {
                let inner = HsrInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Hsr(inner))
            }
            Some(InterfaceType::InfiniBand) => {
                let inner = InfiniBandInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::InfiniBand(inner))
            }
            Some(InterfaceType::Loopback) => {
                let inner = LoopbackInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Loopback(inner))
            }
            Some(InterfaceType::MacSec) => {
                let inner = MacSecInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::MacSec(inner))
            }
            Some(InterfaceType::Ipsec) => {
                let inner = IpsecInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Ipsec(inner))
            }
            Some(InterfaceType::Xfrm) => {
                let inner = XfrmInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Xfrm(inner))
            }
            Some(iface_type) => {
                log::warn!("Unsupported interface type {}", iface_type);
                let inner = UnknownInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Unknown(inner))
            }
            None => {
                let inner = UnknownInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::Unknown(inner))
            }
        }
    }
}

impl Interface {
    /// The interface name.
    pub fn name(&self) -> &str {
        self.base_iface().name.as_str()
    }

    pub(crate) fn is_userspace(&self) -> bool {
        self.base_iface().iface_type.is_userspace()
    }

    pub(crate) fn is_controller(&self) -> bool {
        self.base_iface().iface_type.is_controller()
    }

    /// The interface type
    pub fn iface_type(&self) -> InterfaceType {
        self.base_iface().iface_type.clone()
    }

    pub(crate) fn clone_name_type_only(&self) -> Self {
        match self {
            Self::LinuxBridge(iface) => {
                let mut new_iface = LinuxBridgeInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::LinuxBridge(new_iface)
            }
            Self::Ethernet(iface) => {
                let mut new_iface = EthernetInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                // Do not use veth interface type when clone internally
                new_iface.base.iface_type = InterfaceType::Ethernet;
                Self::Ethernet(new_iface)
            }
            Self::Vlan(iface) => {
                let mut new_iface = VlanInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::Vlan(new_iface)
            }
            Self::Vxlan(iface) => {
                let mut new_iface = VxlanInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::Vxlan(new_iface)
            }
            Self::Dummy(iface) => {
                let mut new_iface = DummyInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::Dummy(new_iface)
            }
            Self::OvsInterface(iface) => {
                let mut new_iface = OvsInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::OvsInterface(new_iface)
            }
            Self::OvsBridge(iface) => {
                let mut new_iface = OvsBridgeInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::OvsBridge(new_iface)
            }
            Self::Bond(iface) => {
                let mut new_iface = BondInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::Bond(new_iface)
            }
            Self::MacVlan(iface) => {
                let mut new_iface = MacVlanInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::MacVlan(new_iface)
            }
            Self::MacVtap(iface) => {
                let mut new_iface = MacVtapInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::MacVtap(new_iface)
            }
            Self::Vrf(iface) => {
                let mut new_iface = VrfInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::Vrf(new_iface)
            }
            Self::Hsr(iface) => {
                let mut new_iface = HsrInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::Hsr(new_iface)
            }
            Self::InfiniBand(iface) => {
                let new_iface = InfiniBandInterface {
                    base: iface.base.clone_name_type_only(),
                    ..Default::default()
                };
                Self::InfiniBand(new_iface)
            }
            Self::Loopback(iface) => {
                let mut new_iface = LoopbackInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::Loopback(new_iface)
            }
            Self::MacSec(iface) => {
                let mut new_iface = MacSecInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::MacSec(new_iface)
            }
            Self::Ipsec(iface) => {
                let mut new_iface = IpsecInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::Ipsec(new_iface)
            }
            Self::Xfrm(iface) => {
                let mut new_iface = XfrmInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::Xfrm(new_iface)
            }
            Self::Unknown(iface) => {
                let mut new_iface = UnknownInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::Unknown(new_iface)
            }
        }
    }

    /// Whether interface is up, default to true.
    pub fn is_up(&self) -> bool {
        self.base_iface().state == InterfaceState::Up
    }

    /// Whether interface is marked as absent.
    pub fn is_absent(&self) -> bool {
        self.base_iface().state == InterfaceState::Absent
    }

    /// Whether interface is marked as down.
    pub fn is_down(&self) -> bool {
        self.base_iface().state == InterfaceState::Down
    }

    /// Whether interface is marked as ignore.
    pub fn is_ignore(&self) -> bool {
        self.base_iface().state == InterfaceState::Ignore
    }

    // Whether desire state only has `name, type, state`.
    pub(crate) fn is_up_exist_config(&self) -> bool {
        self.is_up()
            && match serde_json::to_value(self) {
                Ok(v) => {
                    if let Some(obj) = v.as_object() {
                        // The name, type and state are always been serialized
                        obj.len() == 3
                    } else {
                        log::error!(
                            "BUG: is_up_exist_connection() got \
                            unexpected(not object) serde_json::to_value() \
                            return {}",
                            v
                        );
                        false
                    }
                }
                Err(e) => {
                    log::error!(
                        "BUG: is_up_exist_connection() got unexpected \
                    serde_json::to_value() failure {}",
                        e
                    );
                    false
                }
            }
    }

    /// Whether interface is virtual(can delete from kernel).
    /// Since loopback interface should not be deleted from system,
    /// hence we consider loopback interface as __not__ virtual interface.
    /// Unknown interface is considered as __not__ virtual interface.
    pub fn is_virtual(&self) -> bool {
        !matches!(
            self,
            Self::Ethernet(_)
                | Self::Unknown(_)
                | Self::InfiniBand(_)
                | Self::Loopback(_)
        )
    }

    /// Whether current interface only lives when its control exists.
    /// For example, OpenvSwitch system interface can only exists when
    /// its controller OpenvSwitch bridge exists.
    pub fn need_controller(&self) -> bool {
        matches!(self, Self::OvsInterface(_))
    }

    /// Get reference of its [BaseInterface].
    pub fn base_iface(&self) -> &BaseInterface {
        match self {
            Self::LinuxBridge(iface) => &iface.base,
            Self::Bond(iface) => &iface.base,
            Self::Ethernet(iface) => &iface.base,
            Self::Hsr(iface) => &iface.base,
            Self::Vlan(iface) => &iface.base,
            Self::Vxlan(iface) => &iface.base,
            Self::Dummy(iface) => &iface.base,
            Self::OvsBridge(iface) => &iface.base,
            Self::OvsInterface(iface) => &iface.base,
            Self::MacVlan(iface) => &iface.base,
            Self::MacVtap(iface) => &iface.base,
            Self::Vrf(iface) => &iface.base,
            Self::InfiniBand(iface) => &iface.base,
            Self::Loopback(iface) => &iface.base,
            Self::MacSec(iface) => &iface.base,
            Self::Ipsec(iface) => &iface.base,
            Self::Xfrm(iface) => &iface.base,
            Self::Unknown(iface) => &iface.base,
        }
    }

    pub fn base_iface_mut(&mut self) -> &mut BaseInterface {
        match self {
            Self::LinuxBridge(iface) => &mut iface.base,
            Self::Bond(iface) => &mut iface.base,
            Self::Ethernet(iface) => &mut iface.base,
            Self::Hsr(iface) => &mut iface.base,
            Self::Vlan(iface) => &mut iface.base,
            Self::Vxlan(iface) => &mut iface.base,
            Self::Dummy(iface) => &mut iface.base,
            Self::OvsInterface(iface) => &mut iface.base,
            Self::OvsBridge(iface) => &mut iface.base,
            Self::MacVlan(iface) => &mut iface.base,
            Self::MacVtap(iface) => &mut iface.base,
            Self::Vrf(iface) => &mut iface.base,
            Self::InfiniBand(iface) => &mut iface.base,
            Self::Loopback(iface) => &mut iface.base,
            Self::MacSec(iface) => &mut iface.base,
            Self::Ipsec(iface) => &mut iface.base,
            Self::Xfrm(iface) => &mut iface.base,
            Self::Unknown(iface) => &mut iface.base,
        }
    }

    /// The name of ports.
    /// Return None if its is not controller or not mentioned port section
    pub fn ports(&self) -> Option<Vec<&str>> {
        if self.is_absent() {
            match self {
                Self::LinuxBridge(_) => Some(Vec::new()),
                Self::OvsBridge(_) => Some(Vec::new()),
                Self::Bond(_) => Some(Vec::new()),
                Self::Vrf(_) => Some(Vec::new()),
                _ => None,
            }
        } else {
            match self {
                Self::LinuxBridge(iface) => iface.ports(),
                Self::OvsBridge(iface) => iface.ports(),
                Self::Bond(iface) => iface.ports(),
                Self::Vrf(iface) => iface.ports(),
                _ => None,
            }
        }
    }

    // This function is for pre-edit clean up and check on current, `for_apply`,
    // `for_verify` states.
    //
    // It is plugin's duty to clean up the state for querying before showing to
    // user. Hence please do not use this function for querying.
    // The `is_desired` is used to suppress error checking and logging on
    // non-desired state.
    pub(crate) fn sanitize(
        &mut self,
        is_desired: bool,
    ) -> Result<(), NmstateError> {
        self.base_iface_mut().sanitize(is_desired)?;
        match self {
            Interface::Ethernet(iface) => iface.sanitize()?,
            Interface::Hsr(iface) => iface.sanitize(is_desired)?,
            Interface::LinuxBridge(iface) => iface.sanitize(is_desired)?,
            Interface::OvsInterface(iface) => iface.sanitize(is_desired)?,
            Interface::OvsBridge(iface) => iface.sanitize(is_desired)?,
            Interface::Vrf(iface) => iface.sanitize(is_desired)?,
            Interface::Bond(iface) => iface.sanitize()?,
            Interface::MacVlan(iface) => iface.sanitize(is_desired)?,
            Interface::MacVtap(iface) => iface.sanitize(is_desired)?,
            Interface::Loopback(iface) => iface.sanitize(is_desired)?,
            Interface::MacSec(iface) => iface.sanitize(is_desired)?,
            Interface::Ipsec(iface) => iface.sanitize(is_desired),
            _ => (),
        }
        Ok(())
    }

    pub(crate) fn parent(&self) -> Option<&str> {
        match self {
            Interface::Vlan(vlan) => vlan.parent(),
            Interface::Vxlan(vxlan) => vxlan.parent(),
            Interface::OvsInterface(ovs) => ovs.parent(),
            Interface::MacVlan(vlan) => vlan.parent(),
            Interface::MacVtap(vtap) => vtap.parent(),
            Interface::InfiniBand(ib) => ib.parent(),
            Interface::MacSec(macsec) => macsec.parent(),
            _ => None,
        }
    }

    pub(crate) fn remove_port(&mut self, port_name: &str) {
        if let Interface::LinuxBridge(br_iface) = self {
            br_iface.remove_port(port_name);
        } else if let Interface::OvsBridge(br_iface) = self {
            br_iface.remove_port(port_name);
        } else if let Interface::Bond(iface) = self {
            iface.remove_port(port_name);
        }
    }

    pub(crate) fn change_port_name(
        &mut self,
        org_port_name: &str,
        new_port_name: String,
    ) {
        if let Interface::LinuxBridge(iface) = self {
            iface.change_port_name(org_port_name, new_port_name);
        } else if let Interface::OvsBridge(iface) = self {
            iface.change_port_name(org_port_name, new_port_name);
        } else if let Interface::Bond(iface) = self {
            iface.change_port_name(org_port_name, new_port_name);
        }
    }
}

// The default on enum is experimental, but clippy is suggestion we use
// that experimental derive. Suppress the warning there
#[allow(clippy::derivable_impls)]
impl Default for Interface {
    fn default() -> Self {
        Interface::Unknown(UnknownInterface::default())
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MergedInterface {
    pub(crate) for_verify: Option<Interface>,
    pub(crate) for_apply: Option<Interface>,
    pub(crate) merged: Interface,
    pub(crate) desired: Option<Interface>,
    pub(crate) current: Option<Interface>,
}

impl MergedInterface {
    pub(crate) fn new(
        desired: Option<Interface>,
        current: Option<Interface>,
    ) -> Result<Self, NmstateError> {
        let mut ret = Self {
            for_verify: desired.clone(),
            for_apply: desired.clone(),
            merged: {
                match (desired.as_ref(), current.as_ref()) {
                    (Some(d), Some(c)) => merge_desire_with_current(d, c)?,
                    (Some(d), None) => d.clone(),
                    (None, Some(c)) => c.clone(),
                    (None, None) => {
                        return Err(NmstateError::new(
                            ErrorKind::Bug,
                            "BUG: MergedInterface got both desired \
                            and current set to None"
                                .to_string(),
                        ));
                    }
                }
            },
            desired,
            current,
        };
        ret.pre_inter_ifaces_process();
        Ok(ret)
    }

    pub(crate) fn is_desired(&self) -> bool {
        self.desired.is_some()
    }

    // desired or invoked `mark_as_changed()`.
    pub(crate) fn is_changed(&self) -> bool {
        self.for_apply.is_some()
    }

    fn pre_inter_ifaces_process(&mut self) {
        if self.merged.is_up() && self.is_desired() {
            self.special_merge();
            self.create_ovs_iface_for_empty_ports();
        }
    }

    // This function is designed to hold smart changes or validations
    // which only depend on desire and current status of single interface.
    // This function will be invoked __after__ inter-ifaces process done.
    pub(crate) fn post_inter_ifaces_process(
        &mut self,
    ) -> Result<(), NmstateError> {
        self.preserve_current_controller_info();
        self.post_inter_ifaces_process_base_iface()?;
        self.post_inter_ifaces_process_sriov()?;
        self.post_inter_ifaces_process_vrf()?;
        self.post_inter_ifaces_process_bond()?;

        if let Some(apply_iface) = self.for_apply.as_mut() {
            apply_iface.sanitize(true)?;
        }
        Ok(())
    }

    // After HashMap based merging, extra task required for special use case
    // like.
    fn special_merge(&mut self) {
        if let (Some(desired), Some(current)) =
            (self.desired.as_ref(), self.current.as_ref())
        {
            self.merged
                .base_iface_mut()
                .special_merge(desired.base_iface(), current.base_iface());

            if let Interface::Bond(bond_iface) = &mut self.merged {
                if let (
                    Interface::Bond(des_bond_iface),
                    Interface::Bond(cur_bond_iface),
                ) = (desired, current)
                {
                    bond_iface.special_merge(des_bond_iface, cur_bond_iface);
                }
            } else if let Interface::LinuxBridge(br_iface) = &mut self.merged {
                if let (
                    Interface::LinuxBridge(des_br_iface),
                    Interface::LinuxBridge(cur_br_iface),
                ) = (desired, current)
                {
                    br_iface.special_merge(des_br_iface, cur_br_iface);
                }
            } else if let Interface::OvsBridge(br_iface) = &mut self.merged {
                if let (
                    Interface::OvsBridge(des_br_iface),
                    Interface::OvsBridge(cur_br_iface),
                ) = (desired, current)
                {
                    br_iface.special_merge(des_br_iface, cur_br_iface);
                }
            }
        }
    }

    pub(crate) fn set_copy_from_mac(&mut self, mac: String) {
        if let Some(apply_iface) =
            self.for_apply.as_mut().map(|i| i.base_iface_mut())
        {
            apply_iface.copy_mac_from = None;
            apply_iface.mac_address = Some(mac.to_string());
        }
        if let Some(verify_iface) =
            self.for_verify.as_mut().map(|i| i.base_iface_mut())
        {
            verify_iface.copy_mac_from = None;
            verify_iface.mac_address = Some(mac);
        }
    }

    // Return two list, first is changed port attached to specified interface,
    // second is changed port detached from specified interface.
    pub(crate) fn get_changed_ports(&self) -> Option<(Vec<&str>, Vec<&str>)> {
        let desired_iface = self.desired.as_ref()?;

        if desired_iface.is_absent() {
            if let Some(ports) = self.current.as_ref().and_then(|c| c.ports()) {
                return Some((Vec::new(), ports));
            } else {
                return None;
            }
        }

        let desired_port_names = match desired_iface.ports() {
            Some(p) => HashSet::from_iter(p.iter().cloned()),
            None => {
                // If current interface is in ignore state, even user did not
                // defining ports in desire, we should preserving existing port
                // lists
                if let Some(cur_iface) = self.current.as_ref() {
                    if cur_iface.is_ignore() {
                        match cur_iface.ports().map(|ports| {
                            HashSet::<&str>::from_iter(ports.iter().cloned())
                        }) {
                            Some(p) => p,
                            None => return None,
                        }
                    } else {
                        return None;
                    }
                } else {
                    return None;
                }
            }
        };

        let current_port_names = self
            .current
            .as_ref()
            .and_then(|cur_iface| {
                if cur_iface.is_ignore() {
                    None
                } else {
                    cur_iface.ports()
                }
            })
            .map(|ports| HashSet::<&str>::from_iter(ports.iter().cloned()))
            .unwrap_or_default();

        let mut chg_attached_ports: Vec<&str> = desired_port_names
            .difference(&current_port_names)
            .cloned()
            .collect();
        let chg_detached_ports: Vec<&str> = current_port_names
            .difference(&desired_port_names)
            .cloned()
            .collect();

        // Linux Bridge might have changed configure its port configuration with
        // port name list unchanged.
        // In this case, we should ask LinuxBridgeInterface to generate a list
        // of configure changed port.
        if let (
            Interface::LinuxBridge(des_br_iface),
            Some(Interface::LinuxBridge(cur_br_iface)),
        ) = (desired_iface, self.current.as_ref())
        {
            for port_name in des_br_iface.get_config_changed_ports(cur_br_iface)
            {
                if !chg_attached_ports.contains(&port_name) {
                    chg_attached_ports.push(port_name);
                }
            }
        }
        // Bond might have changed its ports configuration with
        // port name list unchanged.
        // In this case, we should ask BondInterface to generate a new ports
        // configuration list.
        else if let (
            Interface::Bond(des_bond_iface),
            Some(Interface::Bond(cur_bond_iface)),
        ) = (desired_iface, self.current.as_ref())
        {
            for port_name in
                des_bond_iface.get_config_changed_ports(cur_bond_iface)
            {
                if !chg_attached_ports.contains(&port_name) {
                    chg_attached_ports.push(port_name);
                }
            }
        }

        Some((chg_attached_ports, chg_detached_ports))
    }

    // Store `Interface` with name and type into `for_apply`.
    // Do nothing if specified interface is already desired.
    pub(crate) fn mark_as_changed(&mut self) {
        if self.desired.is_none() {
            if let Some(cur_iface) = self.current.as_ref() {
                let iface = cur_iface.clone_name_type_only();
                self.for_apply = Some(iface);
                self.preserve_current_controller_info();
            }
        }
    }

    pub(crate) fn mark_as_absent(&mut self) {
        self.mark_as_changed();
        self.merged.base_iface_mut().state = InterfaceState::Absent;
        if let Some(apply_iface) = self.for_apply.as_mut() {
            apply_iface.base_iface_mut().state = InterfaceState::Absent;
        }
    }

    pub(crate) fn apply_ctrller_change(
        &mut self,
        ctrl_name: String,
        ctrl_type: Option<InterfaceType>,
        ctrl_state: InterfaceState,
    ) -> Result<(), NmstateError> {
        if self.merged.need_controller() && ctrl_name.is_empty() {
            if let Some(org_ctrl) = self
                .current
                .as_ref()
                .and_then(|c| c.base_iface().controller.as_ref())
            {
                if Some(true) == self.for_apply.as_ref().map(|i| i.is_up()) {
                    return Err(NmstateError::new(
                        ErrorKind::InvalidArgument,
                        format!(
                            "Interface {} cannot live without controller, \
                            but it is detached from original controller \
                            {org_ctrl}, cannot apply desired `state:up`",
                            self.merged.name()
                        ),
                    ));
                }
            }
        }

        if !self.is_desired() {
            self.mark_as_changed();
            if ctrl_state == InterfaceState::Up {
                self.merged.base_iface_mut().state = InterfaceState::Up;
                if let Some(apply_iface) = self.for_apply.as_mut() {
                    apply_iface.base_iface_mut().state = InterfaceState::Up;
                }
            }
            log::info!(
                "Include interface {} to edit as its controller required so",
                self.merged.name()
            );
        }
        let apply_iface = if let Some(i) = self.for_apply.as_mut() {
            i
        } else {
            return Err(NmstateError::new(
                ErrorKind::Bug,
                format!(
                    "Reached unreachable code: apply_ctrller_change() \
                    self.for_apply still None: {self:?}"
                ),
            ));
        };

        // Some interface cannot live without controller
        if self.merged.need_controller() && ctrl_name.is_empty() {
            if let Some(org_ctrl) = self
                .current
                .as_ref()
                .and_then(|c| c.base_iface().controller.as_ref())
            {
                log::info!(
                    "Interface {} cannot live without controller, \
                    marking as absent as it has been detached from its \
                    original controller {org_ctrl}",
                    self.merged.name(),
                );
            }
            self.merged.base_iface_mut().state = InterfaceState::Absent;
            apply_iface.base_iface_mut().state = InterfaceState::Absent;
            if let Some(verify_iface) = self.for_verify.as_mut() {
                verify_iface.base_iface_mut().state = InterfaceState::Absent;
            }
        } else {
            apply_iface.base_iface_mut().controller = Some(ctrl_name.clone());
            apply_iface
                .base_iface_mut()
                .controller_type
                .clone_from(&ctrl_type);
            self.merged.base_iface_mut().controller = Some(ctrl_name);
            self.merged.base_iface_mut().controller_type = ctrl_type;
            if !self.merged.base_iface().can_have_ip() {
                self.merged.base_iface_mut().ipv4 = None;
                self.merged.base_iface_mut().ipv6 = None;
            }
        }
        Ok(())
    }

    fn preserve_current_controller_info(&mut self) {
        if let Some(apply_iface) = self.for_apply.as_mut() {
            if apply_iface.base_iface().controller.is_none() {
                if let Some(cur_iface) = self.current.as_ref() {
                    if cur_iface.base_iface().controller.as_ref().is_some() {
                        apply_iface
                            .base_iface_mut()
                            .controller
                            .clone_from(&cur_iface.base_iface().controller);
                        apply_iface
                            .base_iface_mut()
                            .controller_type
                            .clone_from(
                                &cur_iface.base_iface().controller_type,
                            );
                    }
                }
            }
        }
    }
}

// This function is merging all properties without known their meanings.
// When special merging required, please do that in `MergedInterface.process()`,
// after merged using stored `desired` and `current`.
fn merge_desire_with_current(
    desired: &Interface,
    current: &Interface,
) -> Result<Interface, NmstateError> {
    let mut desired_value = serde_json::to_value(desired)?;
    let current_value = serde_json::to_value(current)?;
    merge_json_value(&mut desired_value, &current_value);

    let iface: Interface = serde_json::from_value(desired_value)?;

    Ok(iface)
}

#[derive(
    Debug,
    Clone,
    Copy,
    PartialEq,
    Eq,
    Hash,
    PartialOrd,
    Ord,
    Serialize,
    Deserialize,
)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
/// Interface Identifier defines the method for network backend on matching
/// network interface
pub enum InterfaceIdentifier {
    /// Use interface name to match the network interface, default value.
    /// Deserialize and serialize from/to 'name'.
    Name,
    /// Use interface MAC address to match the network interface.
    /// Deserialize and serialize from/to 'mac-address'.
    MacAddress,
}

impl Default for InterfaceIdentifier {
    fn default() -> Self {
        Self::Name
    }
}

impl InterfaceIdentifier {
    pub fn is_default(&self) -> bool {
        self == &InterfaceIdentifier::default()
    }
}
