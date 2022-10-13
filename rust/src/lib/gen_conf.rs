// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use serde::Deserialize;

use crate::{
    nm::nm_gen_conf, ErrorKind, EthernetInterface, Interface, Interfaces,
    NetworkState, NmstateError,
};

impl NetworkState {
    pub fn gen_conf(
        &self,
    ) -> Result<HashMap<String, Vec<(String, String)>>, NmstateError> {
        let mut ret = HashMap::new();
        let mut self_clone = self.clone();
        self_clone.interfaces.set_unknown_iface_to_eth()?;
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

    fn set_unknown_iface_to_eth(&mut self) -> Result<(), NmstateError> {
        let mut new_ifaces = Vec::new();
        for iface in self.kernel_ifaces.values_mut() {
            if let Interface::Unknown(iface) = iface {
                log::warn!(
                    "Setting unknown type interface {} to ethernet",
                    iface.base.name.as_str()
                );
                let iface_value = match serde_json::to_value(&iface) {
                    Ok(mut v) => {
                        if let Some(v) = v.as_object_mut() {
                            v.insert(
                                "type".to_string(),
                                serde_json::Value::String(
                                    "ethernet".to_string(),
                                ),
                            );
                        }
                        v
                    }
                    Err(e) => {
                        return Err(NmstateError::new(
                            ErrorKind::Bug,
                            format!(
                                "BUG: Failed to convert {:?} to serde_json \
                                value: {}",
                                iface, e
                            ),
                        ));
                    }
                };
                match EthernetInterface::deserialize(&iface_value) {
                    Ok(i) => new_ifaces.push(i),
                    Err(e) => {
                        return Err(NmstateError::new(
                            ErrorKind::InvalidArgument,
                            format!(
                                "Invalid property for ethernet interface: {}",
                                e
                            ),
                        ));
                    }
                }
            }
        }
        for iface in new_ifaces {
            self.kernel_ifaces.insert(
                iface.base.name.to_string(),
                Interface::Ethernet(iface),
            );
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use crate::{Interface, InterfaceType, Interfaces};

    #[test]
    fn test_gen_conf_change_unknown_to_eth() {
        let mut ifaces: Interfaces = serde_yaml::from_str(
            r#"---
- name: foo
  state: up
  ethernet:
    speed: 1000
"#,
        )
        .unwrap();

        ifaces.set_unknown_iface_to_eth().unwrap();

        let ifaces = ifaces.to_vec();

        assert_eq!(ifaces.len(), 1);
        if let Interface::Ethernet(eth_iface) = ifaces[0] {
            assert_eq!(eth_iface.base.iface_type, InterfaceType::Ethernet);
            assert_eq!(eth_iface.ethernet.as_ref().unwrap().speed, Some(1000));
        } else {
            panic!("Expecting ethernet interface");
        }
    }
}
