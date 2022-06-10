use std::collections::HashMap;

use crate::{net_state::NetworkState, nm::nm_gen_conf, NmstateError};

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
