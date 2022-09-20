// SPDX-License-Identifier: Apache-2.0

use crate::{
    state::get_json_value_difference, ErrorKind, Interface, InterfaceType,
    LinuxBridgeInterface, NmstateError,
};

impl Interface {
    pub(crate) fn remove_port(&mut self, port_name: &str) {
        if let Interface::LinuxBridge(br_iface) = self {
            br_iface.remove_port(port_name);
        } else if let Interface::OvsBridge(br_iface) = self {
            br_iface.remove_port(port_name);
        } else if let Interface::Bond(iface) = self {
            iface.remove_port(port_name);
        }
    }

    pub(crate) fn pre_verify_cleanup(
        &mut self,
        pre_apply_current: Option<&Self>,
    ) {
        self.base_iface_mut()
            .pre_verify_cleanup(pre_apply_current.map(|i| i.base_iface()));
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
                iface.pre_verify_cleanup(pre_apply_current);
            }
            _ => (),
        }
    }

    pub(crate) fn verify(
        &self,
        pre_apply_cur_iface: Option<&Self>,
        current: &Self,
    ) -> Result<(), NmstateError> {
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
        current_clone.pre_verify_cleanup(None);
        self_clone.pre_verify_cleanup(pre_apply_cur_iface);
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
                    log::error!("{}", e);
                    return Err(e);
                }
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
            Self::Unknown(_) | Self::Dummy(_) | Self::OvsInterface(_) => (),
        }
    }
}
