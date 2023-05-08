// SPDX-License-Identifier: Apache-2.0

use crate::{
    state::get_json_value_difference, ErrorKind, Interface, InterfaceType,
    LinuxBridgeInterface, NmstateError,
};

impl Interface {
    // This function will clean up post-apply current state before verification
    pub(crate) fn sanitize_current_for_verify(&mut self) {
        self.base_iface_mut().sanitize_current_for_verify();
        if let Interface::LinuxBridge(iface) = self {
            iface.sanitize_current_for_verify()
        }
        if let Interface::OvsBridge(iface) = self {
            iface.sanitize_current_for_verify()
        }
    }

    // This function will clean up desired state before verification
    pub(crate) fn sanitize_desired_for_verify(&mut self) {
        self.base_iface_mut().sanitize_desired_for_verify();
        if let Interface::Ethernet(iface) = self {
            iface.sanitize_desired_for_verify();
        }
    }

    pub(crate) fn verify(&self, current: &Self) -> Result<(), NmstateError> {
        let mut current = current.clone();
        self.process_allow_extra_address(&mut current);

        let self_value = serde_json::to_value(self)?;
        let current_value = serde_json::to_value(&current)?;

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
                    log::error!("{}", e);
                    return Err(e);
                }
            }

            Err(NmstateError::new(
                ErrorKind::VerificationError,
                format!(
                    "Verification failure: {reference} desire '{desire}', \
                    current '{current}'"
                ),
            ))
        } else {
            Ok(())
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
                    log::warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface,
                        other
                    );
                }
            }
            Self::Bond(iface) => {
                if let Self::Bond(other_iface) = other {
                    iface.update_bond(other_iface);
                } else {
                    log::warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface,
                        other
                    );
                }
            }
            Self::Ethernet(iface) => {
                if let Self::Ethernet(other_iface) = other {
                    iface.update_ethernet(other_iface);
                    iface.update_veth(other_iface);
                } else {
                    log::warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface,
                        other
                    );
                }
            }
            Self::Vlan(iface) => {
                if let Self::Vlan(other_iface) = other {
                    iface.update_vlan(other_iface);
                } else {
                    log::warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface,
                        other
                    );
                }
            }
            Self::Vxlan(iface) => {
                if let Self::Vxlan(other_iface) = other {
                    iface.update_vxlan(other_iface);
                } else {
                    log::warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface,
                        other
                    );
                }
            }
            Self::OvsBridge(iface) => {
                if let Self::OvsBridge(other_iface) = other {
                    iface.update_ovs_bridge(other_iface);
                } else {
                    log::warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface,
                        other
                    );
                }
            }
            Self::MacVlan(iface) => {
                if let Self::MacVlan(other_iface) = other {
                    iface.update_mac_vlan(other_iface);
                } else {
                    log::warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface,
                        other
                    );
                }
            }
            Self::MacVtap(iface) => {
                if let Self::MacVtap(other_iface) = other {
                    iface.update_mac_vtap(other_iface);
                } else {
                    log::warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface,
                        other
                    );
                }
            }
            Self::Vrf(iface) => {
                if let Self::Vrf(other_iface) = other {
                    iface.update_vrf(other_iface);
                } else {
                    log::warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface,
                        other
                    );
                }
            }
            Self::InfiniBand(iface) => {
                if let Self::InfiniBand(other_iface) = other {
                    iface.update_ib(other_iface);
                } else {
                    log::warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface,
                        other
                    );
                }
            }
            Self::OvsInterface(iface) => {
                if let Self::OvsInterface(other_iface) = other {
                    iface.update_ovs_iface(other_iface);
                } else {
                    log::warn!(
                        "Don't know how to update iface {:?} with {:?}",
                        iface,
                        other
                    );
                }
            }
            _ => (),
        }
    }
}

impl InterfaceType {
    pub(crate) const SUPPORTED_LIST: [InterfaceType; 14] = [
        InterfaceType::Bond,
        InterfaceType::LinuxBridge,
        InterfaceType::Dummy,
        InterfaceType::Ethernet,
        InterfaceType::Veth,
        InterfaceType::MacVtap,
        InterfaceType::MacVlan,
        InterfaceType::OvsBridge,
        InterfaceType::OvsInterface,
        InterfaceType::Vlan,
        InterfaceType::Vxlan,
        InterfaceType::InfiniBand,
        InterfaceType::Loopback,
        InterfaceType::Vrf,
    ];
}
