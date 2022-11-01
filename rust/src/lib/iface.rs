// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Deserializer, Serialize, Serializer};

use crate::{
    BaseInterface, BondInterface, DummyInterface, EthernetInterface,
    InfiniBandInterface, LinuxBridgeInterface, MacVlanInterface,
    MacVtapInterface, NmstateError, OvsBridgeInterface, OvsInterface,
    VlanInterface, VrfInterface, VxlanInterface,
};

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
#[non_exhaustive]
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
    InfiniBand,
    /// Unknown interface.
    Unknown,
    /// Reserved for future use.
    Other(String),
}

impl Default for InterfaceType {
    fn default() -> Self {
        Self::Unknown
    }
}

impl From<&str> for InterfaceType {
    fn from(s: &str) -> Self {
        match s {
            "bond" => InterfaceType::Bond,
            "linux-bridge" => InterfaceType::LinuxBridge,
            "dummy" => InterfaceType::Dummy,
            "ethernet" => InterfaceType::Ethernet,
            "loopback" => InterfaceType::Loopback,
            "mac-vlan" => InterfaceType::MacVlan,
            "mac-vtap" => InterfaceType::MacVtap,
            "ovs-bridge" => InterfaceType::OvsBridge,
            "ovs-interface" => InterfaceType::OvsInterface,
            "veth" => InterfaceType::Veth,
            "vlan" => InterfaceType::Vlan,
            "vrf" => InterfaceType::Vrf,
            "vxlan" => InterfaceType::Vxlan,
            "infiniband" => InterfaceType::InfiniBand,
            "unknown" => InterfaceType::Unknown,
            _ => InterfaceType::Other(s.to_string()),
        }
    }
}

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
                InterfaceType::Other(ref s) => s,
            }
        )
    }
}

impl Serialize for InterfaceType {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(format!("{self}").as_str())
    }
}

impl<'de> Deserialize<'de> for InterfaceType {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let v = serde_json::Value::deserialize(deserializer)?;
        match v.as_str() {
            Some(s) => Ok(InterfaceType::from(s)),
            None => Ok(InterfaceType::Unknown),
        }
    }
}

impl InterfaceType {
    const USERSPACE_IFACE_TYPES: [Self; 1] = [Self::OvsBridge];
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

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
/// The state of interface
pub enum InterfaceState {
    /// Interface is up and running.
    /// Deserialize and serialize from/to 'down'.
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
    /// Deserialize and serialize from/to 'ignore'.
    Ignore,
}

impl Default for InterfaceState {
    fn default() -> Self {
        Self::Unknown
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
        let v = serde_json::Value::deserialize(deserializer)?;
        let mut base_value = serde_json::map::Map::new();
        if let Some(n) = v.get("name") {
            base_value.insert("name".to_string(), n.clone());
        }
        if let Some(s) = v.get("state") {
            base_value.insert("state".to_string(), s.clone());
        }
        // The BaseInterface will only have name and state
        // These two properties are also stored in `other` for serializing
        ret.base = BaseInterface::deserialize(
            serde_json::value::Value::Object(base_value),
        )
        .map_err(serde::de::Error::custom)?;
        ret.other = v;
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
            Some(InterfaceType::InfiniBand) => {
                let inner = InfiniBandInterface::deserialize(v)
                    .map_err(serde::de::Error::custom)?;
                Ok(Interface::InfiniBand(inner))
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

    pub(crate) fn set_iface_type(&mut self, iface_type: InterfaceType) {
        self.base_iface_mut().iface_type = iface_type;
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
            Self::InfiniBand(iface) => {
                let new_iface = InfiniBandInterface {
                    base: iface.base.clone_name_type_only(),
                    ..Default::default()
                };
                Self::InfiniBand(new_iface)
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

    /// Whether interface is virtual(no real hardware).
    /// Unknown interface is considered as __not__ virtual interface.
    pub fn is_virtual(&self) -> bool {
        !matches!(
            self,
            Self::Ethernet(_) | Self::Unknown(_) | Self::InfiniBand(_)
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
            Self::Vlan(iface) => &iface.base,
            Self::Vxlan(iface) => &iface.base,
            Self::Dummy(iface) => &iface.base,
            Self::OvsBridge(iface) => &iface.base,
            Self::OvsInterface(iface) => &iface.base,
            Self::MacVlan(iface) => &iface.base,
            Self::MacVtap(iface) => &iface.base,
            Self::Vrf(iface) => &iface.base,
            Self::InfiniBand(iface) => &iface.base,
            Self::Unknown(iface) => &iface.base,
        }
    }

    pub(crate) fn base_iface_mut(&mut self) -> &mut BaseInterface {
        match self {
            Self::LinuxBridge(iface) => &mut iface.base,
            Self::Bond(iface) => &mut iface.base,
            Self::Ethernet(iface) => &mut iface.base,
            Self::Vlan(iface) => &mut iface.base,
            Self::Vxlan(iface) => &mut iface.base,
            Self::Dummy(iface) => &mut iface.base,
            Self::OvsInterface(iface) => &mut iface.base,
            Self::OvsBridge(iface) => &mut iface.base,
            Self::MacVlan(iface) => &mut iface.base,
            Self::MacVtap(iface) => &mut iface.base,
            Self::Vrf(iface) => &mut iface.base,
            Self::InfiniBand(iface) => &mut iface.base,
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

    pub(crate) fn pre_edit_cleanup(
        &mut self,
        current: Option<&Self>,
    ) -> Result<(), NmstateError> {
        self.base_iface_mut()
            .pre_edit_cleanup(current.map(|i| i.base_iface()))?;
        match self {
            Interface::LinuxBridge(iface) => iface.pre_edit_cleanup(),
            Interface::Ethernet(iface) => iface.pre_edit_cleanup(),
            Interface::OvsInterface(iface) => iface.pre_edit_cleanup(),
            Interface::Vrf(iface) => iface.pre_edit_cleanup(current),
            Interface::Bond(iface) => iface.pre_edit_cleanup(current),
            Interface::MacVlan(iface) => iface.pre_edit_cleanup(),
            Interface::MacVtap(iface) => iface.pre_edit_cleanup(),
            _ => Ok(()),
        }
    }

    pub(crate) fn parent(&self) -> Option<&str> {
        match self {
            Interface::Vlan(vlan) => vlan.parent(),
            Interface::Vxlan(vxlan) => vxlan.parent(),
            Interface::OvsInterface(ovs) => ovs.parent(),
            Interface::MacVlan(vlan) => vlan.parent(),
            Interface::MacVtap(vtap) => vtap.parent(),
            Interface::InfiniBand(ib) => ib.parent(),
            _ => None,
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
