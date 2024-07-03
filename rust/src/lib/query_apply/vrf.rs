// SPDX-License-Identifier: Apache-2.0

use crate::{InterfaceType, VrfConfig, VrfInterface};

impl VrfInterface {
    pub(crate) fn update_vrf(&mut self, other: &VrfInterface) {
        // TODO: this should be done by Trait
        if let Some(vrf_conf) = &mut self.vrf {
            vrf_conf.update(other.vrf.as_ref());
        } else {
            self.vrf.clone_from(&other.vrf);
        }
    }

    pub(crate) fn set_port_mac_and_type(
        &mut self,
        port_name: &str,
        mac_address: &str,
        port_iface_type: InterfaceType,
    ) {
        if let Some(ports_config) = self
            .vrf
            .as_mut()
            .and_then(|b| b.ports_config.as_deref_mut())
        {
            if ports_config
                .iter_mut()
                .find_map(|p| {
                    if p.name.as_deref() == Some(port_name) {
                        p.permanent_mac_address = Some(mac_address.to_string());
                        p.iface_type = Some(port_iface_type);
                        Some(())
                    } else {
                        None
                    }
                })
                .is_some()
            {
                return;
            }
        }

        log::error!(
            "BUG: VrfInterface::set_port_mac_and_type() failed to set \
             port {} with mac_address {} type {}: {:?}",
            port_name,
            mac_address,
            port_iface_type,
            self
        );
    }
}

impl VrfConfig {
    fn update(&mut self, other: Option<&Self>) {
        if let Some(other) = other {
            self.port.clone_from(&other.port);
            self.table_id = other.table_id;
        }
    }
}
