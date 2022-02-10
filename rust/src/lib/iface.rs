use log::{error, warn};
use serde::{Deserialize, Deserializer, Serialize};

use crate::{
    state::get_json_value_difference, BaseInterface, BondInterface,
    DummyInterface, ErrorKind, EthernetInterface, LinuxBridgeInterface,
    MacVlanInterface, MacVtapInterface, NmstateError, OvsBridgeInterface,
    OvsInterface, VlanInterface, VrfInterface, VxlanInterface,
};

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum InterfaceType {
    Bond,
    LinuxBridge,
    Dummy,
    Ethernet,
    Loopback,
    MacVlan,
    MacVtap,
    OvsBridge,
    OvsInterface,
    Tun,
    Veth,
    Vlan,
    Vrf,
    Vxlan,
    Unknown,
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
            "macvlan" => InterfaceType::MacVlan,
            "macvtap" => InterfaceType::MacVtap,
            "ovs-bridge" => InterfaceType::OvsBridge,
            "ovs-interface" => InterfaceType::OvsInterface,
            "tun" => InterfaceType::Tun,
            "veth" => InterfaceType::Veth,
            "vlan" => InterfaceType::Vlan,
            "vrf" => InterfaceType::Vrf,
            "vxlan" => InterfaceType::Vxlan,
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
                InterfaceType::MacVlan => "macvlan",
                InterfaceType::MacVtap => "macvtap",
                InterfaceType::OvsBridge => "ovs-bridge",
                InterfaceType::OvsInterface => "ovs-interface",
                InterfaceType::Tun => "tun",
                InterfaceType::Veth => "veth",
                InterfaceType::Vlan => "vlan",
                InterfaceType::Vrf => "vrf",
                InterfaceType::Vxlan => "vxlan",
                InterfaceType::Unknown => "unknown",
                InterfaceType::Other(ref s) => s,
            }
        )
    }
}

impl InterfaceType {
    const USERSPACE_IFACE_TYPES: [Self; 1] = [Self::OvsBridge];
    const CONTROLLER_IFACES_TYPES: [Self; 4] =
        [Self::Bond, Self::LinuxBridge, Self::OvsBridge, Self::Vrf];

    // Unknown and other interfaces are also considered as userspace
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

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum InterfaceState {
    Up,
    Down,
    Absent,
    Unknown,
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
            _ => Self::Unknown,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[non_exhaustive]
pub struct UnknownInterface {
    #[serde(flatten)]
    pub base: BaseInterface,
}

impl UnknownInterface {
    pub fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "kebab-case", untagged)]
#[non_exhaustive]
pub enum Interface {
    Bond(BondInterface),
    Dummy(DummyInterface),
    Ethernet(EthernetInterface),
    LinuxBridge(LinuxBridgeInterface),
    OvsBridge(OvsBridgeInterface),
    OvsInterface(OvsInterface),
    Unknown(UnknownInterface),
    Vlan(VlanInterface),
    Vxlan(VxlanInterface),
    MacVlan(MacVlanInterface),
    MacVtap(MacVtapInterface),
    Vrf(VrfInterface),
}

impl<'de> Deserialize<'de> for Interface {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let v = serde_json::Value::deserialize(deserializer)?;
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
            Some(iface_type) => {
                warn!("Unsupported interface type {}", iface_type);
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
            Self::Unknown(iface) => {
                let mut new_iface = UnknownInterface::new();
                new_iface.base = iface.base.clone_name_type_only();
                Self::Unknown(new_iface)
            }
        }
    }

    pub fn is_up(&self) -> bool {
        self.base_iface().state == InterfaceState::Up
    }

    pub fn is_absent(&self) -> bool {
        self.base_iface().state == InterfaceState::Absent
    }

    pub fn is_down(&self) -> bool {
        self.base_iface().state == InterfaceState::Down
    }

    pub fn is_virtual(&self) -> bool {
        !matches!(self, Self::Ethernet(_) | Self::Unknown(_))
    }

    // OVS Interface should be deleted along with its controller
    pub fn need_controller(&self) -> bool {
        matches!(self, Self::OvsInterface(_))
    }

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
            Self::Unknown(iface) => &mut iface.base,
        }
    }

    // Return None if its is not controller
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

    pub fn update(&mut self, other: &Interface) {
        self.base_iface_mut().update(other.base_iface());
        if let Self::Unknown(_) = other {
            return;
        }
        match self {
            Self::LinuxBridge(iface) => {
                if let Self::LinuxBridge(other_iface) = other {
                    iface.update_bridge(other_iface);
                } else {
                    warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface, other
                    );
                }
            }
            Self::Bond(iface) => {
                if let Self::Bond(other_iface) = other {
                    iface.update_bond(other_iface);
                } else {
                    warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface, other
                    );
                }
            }
            Self::Ethernet(iface) => {
                if let Self::Ethernet(other_iface) = other {
                    iface.update_ethernet(other_iface);
                    iface.update_veth(other_iface);
                } else {
                    warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface, other
                    );
                }
            }
            Self::Vlan(iface) => {
                if let Self::Vlan(other_iface) = other {
                    iface.update_vlan(other_iface);
                } else {
                    warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface, other
                    );
                }
            }
            Self::Vxlan(iface) => {
                if let Self::Vxlan(other_iface) = other {
                    iface.update_vxlan(other_iface);
                } else {
                    warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface, other
                    );
                }
            }
            Self::OvsBridge(iface) => {
                if let Self::OvsBridge(other_iface) = other {
                    iface.update_ovs_bridge(other_iface);
                } else {
                    warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface, other
                    );
                }
            }
            Self::MacVlan(iface) => {
                if let Self::MacVlan(other_iface) = other {
                    iface.update_mac_vlan(other_iface);
                } else {
                    warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface, other
                    );
                }
            }
            Self::MacVtap(iface) => {
                if let Self::MacVtap(other_iface) = other {
                    iface.update_mac_vtap(other_iface);
                } else {
                    warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface, other
                    );
                }
            }
            Self::Vrf(iface) => {
                if let Self::Vrf(other_iface) = other {
                    iface.update_vrf(other_iface);
                } else {
                    warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface, other
                    );
                }
            }
            Self::Unknown(_) | Self::Dummy(_) | Self::OvsInterface(_) => (),
        }
    }

    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.base_iface_mut().pre_verify_cleanup();
        match self {
            Self::LinuxBridge(ref mut iface) => {
                iface.pre_verify_cleanup();
            }
            Self::Bond(ref mut iface) => {
                iface.pre_verify_cleanup();
            }
            Self::Ethernet(ref mut iface) => {
                iface.pre_verify_cleanup();
            }
            Self::OvsBridge(ref mut iface) => {
                iface.pre_verify_cleanup();
            }
            Self::Vrf(ref mut iface) => {
                iface.pre_verify_cleanup();
            }
            _ => (),
        }
    }

    pub(crate) fn pre_edit_cleanup(&mut self) -> Result<(), NmstateError> {
        self.base_iface_mut().pre_edit_cleanup()?;
        if let Interface::Ethernet(iface) = self {
            if iface.veth.is_some() {
                iface.base.iface_type = InterfaceType::Veth;
            }
        }
        Ok(())
    }

    pub(crate) fn verify(&self, current: &Self) -> Result<(), NmstateError> {
        let mut self_clone = self.clone();
        let mut current_clone = current.clone();
        // In order to allow desire interface to determine whether it can
        // hold IP or not, we copy controller information from current to desire
        // Use case: User desire ipv4 enabled: false on a bridge port, but
        // current show ipv4 as None.
        if current_clone.base_iface().controller.is_some()
            && self_clone.base_iface().controller.is_none()
        {
            self_clone.base_iface_mut().controller =
                current_clone.base_iface().controller.clone();
            self_clone.base_iface_mut().controller_type =
                current_clone.base_iface().controller_type.clone();
        }
        self_clone.pre_verify_cleanup();
        current_clone.pre_verify_cleanup();
        if self_clone.iface_type() == InterfaceType::Unknown {
            current_clone.base_iface_mut().iface_type = InterfaceType::Unknown;
        }

        let self_value = serde_json::to_value(&self_clone)?;
        let current_value = serde_json::to_value(&current_clone)?;

        if let Some((reference, desire, current)) = get_json_value_difference(
            format!("{}.interface", self.name()),
            &self_value,
            &current_value,
        ) {
            // Linux Bridge on 250 kernel HZ and 100 user HZ system(e.g.
            // Ubuntu) will have round up which lead to 1 difference.
            if let (
                serde_json::Value::Number(des),
                serde_json::Value::Number(cur),
            ) = (desire, current)
            {
                if desire.as_u64().unwrap_or(0) as i128
                    - cur.as_u64().unwrap_or(0) as i128
                    == 1
                    && LinuxBridgeInterface::is_interger_rounded_up(&reference)
                {
                    let e = NmstateError::new(
                        ErrorKind::KernelIntegerRoundedError,
                        format!(
                            "Linux kernel configured with 250 HZ \
                                will round up/down the integer in linux \
                                bridge {} option '{}' from {:?} to {:?}.",
                            self.name(),
                            reference,
                            des,
                            cur
                        ),
                    );
                    error!("{}", e);
                    return Err(e);
                }
            }

            if reference.contains("link-aggregation.options") {
                return Ok(());
            }

            Err(NmstateError::new(
                ErrorKind::VerificationError,
                format!(
                    "Verification failure: {} desire '{}', current '{}'",
                    reference, desire, current
                ),
            ))
        } else {
            Ok(())
        }
    }

    pub(crate) fn validate(&self) -> Result<(), NmstateError> {
        match self {
            Interface::LinuxBridge(iface) => iface.validate(),
            Interface::Bond(iface) => iface.validate(),
            Interface::MacVlan(iface) => iface.validate(),
            Interface::MacVtap(iface) => iface.validate(),
            _ => Ok(()),
        }
    }

    pub(crate) fn remove_port(&mut self, port_name: &str) {
        if let Interface::LinuxBridge(br_iface) = self {
            br_iface.remove_port(port_name);
        } else if let Interface::Bond(iface) = self {
            iface.remove_port(port_name);
        }
    }

    pub(crate) fn parent(&self) -> Option<&str> {
        match self {
            Interface::Vlan(vlan) => vlan.parent(),
            Interface::Vxlan(vxlan) => vxlan.parent(),
            Interface::OvsInterface(ovs) => ovs.parent(),
            Interface::MacVlan(vlan) => vlan.parent(),
            Interface::MacVtap(vtap) => vtap.parent(),
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
