// SPDX-License-Identifier: Apache-2.0

use crate::{InterfaceMatchRule, VrfConfig, VrfInterface};

impl VrfInterface {
    pub(crate) fn update_vrf(&mut self, other: &VrfInterface) {
        // TODO: this should be done by Trait
        if let Some(vrf_conf) = &mut self.vrf {
            vrf_conf.update(other.vrf.as_ref());
        } else {
            self.vrf.clone_from(&other.vrf);
        }
    }

    pub(crate) fn set_port_iface_match(
        &mut self,
        port_name: &str,
        iface_match: &InterfaceMatchRule,
    ) {
        if let Some(ports_config) = self
            .vrf
            .as_mut()
            .and_then(|b| b.ports_config.as_deref_mut())
        {
            if ports_config
                .iter_mut()
                .find_map(|p| {
                    if p.name.as_str() == port_name {
                        p.iface_match = Some(iface_match.clone());
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
            "BUG: VrfInterface::set_port_iface_match() failed to find \
            port with name {port_name}: {self:?}",
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
