// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{nm::nm_gen_conf, MergedNetworkState, NetworkState, NmstateError};

impl NetworkState {
    /// Generate offline network configurations.
    /// Currently only support generate NetworkManager key file out of
    /// NetworkState.
    ///
    /// The output is a [HashMap] with backend name as key and
    /// `Vec<(config_file_name, config_content>)>` as value.
    ///
    /// The backend name for NetworkManager is `NetworkManager`.
    pub fn gen_conf(
        &self,
    ) -> Result<HashMap<String, Vec<(String, String)>>, NmstateError> {
        let mut ret = HashMap::new();
        let merged_state = MergedNetworkState::new(
            self.clone(),
            NetworkState::new(),
            true,  // gen_conf mode
            false, // memory only
        )?;
        ret.insert("NetworkManager".to_string(), nm_gen_conf(&merged_state)?);
        Ok(ret)
    }
}

#[cfg(test)]
mod tests {
    use crate::{Interface, InterfaceType, Interfaces};

    #[test]
    fn test_gen_conf_change_unknown_to_eth() {
        let mut ifaces: Interfaces = serde_yaml::from_str(
            r"---
- name: foo
  state: up
  ethernet:
    speed: 1000
",
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
