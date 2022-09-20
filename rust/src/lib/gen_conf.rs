// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{
    nm::nm_gen_conf, EthernetInterface, Interface, InterfaceType, Interfaces,
    NetworkState, NmstateError,
};

impl NetworkState {
    pub fn gen_conf(
        &self,
    ) -> Result<HashMap<String, Vec<(String, String)>>, NmstateError> {
        let mut ret = HashMap::new();
        let mut self_clone = self.clone();
        self_clone.interfaces.set_unknown_iface_to_eth();
        self_clone.interfaces.set_missing_port_to_eth();
        let (add_net_state, _, _) =
            self_clone.gen_state_for_apply(&Self::new())?;
        ret.insert("NetworkManager".to_string(), nm_gen_conf(&add_net_state)?);
        Ok(ret)
    }
}

impl Interfaces {
    fn set_missing_port_to_eth(&mut self) {
        let mut iface_names_to_add = Vec::new();
        for iface in
            self.kernel_ifaces.values().chain(self.user_ifaces.values())
        {
            if let Some(ports) = iface.ports() {
                for port in ports {
                    if !self.kernel_ifaces.contains_key(port) {
                        iface_names_to_add.push(port.to_string());
                    }
                }
            }
        }
        for iface_name in iface_names_to_add {
            let mut iface = EthernetInterface::default();
            iface.base.name = iface_name.clone();
            log::warn!("Assuming undefined port {} as ethernet", iface_name);
            self.kernel_ifaces
                .insert(iface_name, Interface::Ethernet(iface));
        }
    }

    fn set_unknown_iface_to_eth(&mut self) {
        for iface in self.kernel_ifaces.values_mut() {
            if iface.iface_type() == InterfaceType::Unknown {
                log::warn!(
                    "Setting unknown type interface {} to ethernet",
                    iface.name()
                );
                iface.base_iface_mut().iface_type = InterfaceType::Ethernet;
            }
        }
    }
}
