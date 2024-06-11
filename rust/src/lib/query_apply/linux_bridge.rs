// SPDX-License-Identifier: Apache-2.0

use crate::{
    BridgePortVlanConfig, Interface, LinuxBridgeConfig, LinuxBridgeInterface,
    MergedInterface,
};

impl LinuxBridgeInterface {
    pub(crate) const INTEGER_ROUNDED_OPTIONS: [&'static str; 5] = [
        "interface.bridge.options.multicast-last-member-interval",
        "interface.bridge.options.multicast-membership-interval",
        "interface.bridge.options.multicast-querier-interval",
        "interface.bridge.options.multicast-query-response-interval",
        "interface.bridge.options.multicast-startup-query-interval",
    ];

    pub(crate) fn sanitize_current_for_verify(&mut self) {
        self.treat_none_vlan_as_empty_dict();
    }

    // This is for verifying when user desire `vlan: {}` for resetting VLAN
    // filtering, the new current state will show as `vlan: None`.
    fn treat_none_vlan_as_empty_dict(&mut self) {
        if let Some(port_confs) = self
            .bridge
            .as_mut()
            .and_then(|br_conf| br_conf.port.as_mut())
        {
            for port_conf in port_confs {
                if port_conf.vlan.is_none() {
                    port_conf.vlan = Some(BridgePortVlanConfig::new());
                }
            }
        }
    }

    pub(crate) fn update_bridge(&mut self, other: &LinuxBridgeInterface) {
        if let Some(br_conf) = &mut self.bridge {
            br_conf.update(other.bridge.as_ref());
        } else {
            self.bridge.clone_from(&other.bridge);
        }
    }

    // With 250 kernel HZ(Ubuntu kernel) and 100 user HZ, some linux bridge
    // kernel option value will be rounded up with 1 difference which lead to
    // verification error.
    pub(crate) fn is_interger_rounded_up(prop_full_name: &str) -> bool {
        for allowed_prop_name in &Self::INTEGER_ROUNDED_OPTIONS {
            if prop_full_name.ends_with(allowed_prop_name) {
                return true;
            }
        }
        false
    }
}

impl LinuxBridgeConfig {
    pub(crate) fn update(&mut self, other: Option<&LinuxBridgeConfig>) {
        if let Some(other) = other {
            self.options.clone_from(&other.options);
            self.port.clone_from(&other.port);
        }
    }
}

impl MergedInterface {
    pub(crate) fn is_default_pvid_changed(&self) -> bool {
        let des_default_pvid = if let Some(Interface::LinuxBridge(des_iface)) =
            self.for_apply.as_ref()
        {
            des_iface
                .bridge
                .as_ref()
                .and_then(|b| b.options.as_ref())
                .and_then(|o| o.vlan_default_pvid.as_ref())
        } else {
            None
        };

        let cur_default_pvid = if let Some(Interface::LinuxBridge(cur_iface)) =
            self.current.as_ref()
        {
            cur_iface
                .bridge
                .as_ref()
                .and_then(|b| b.options.as_ref())
                .and_then(|o| o.vlan_default_pvid.as_ref())
        } else {
            None
        };

        des_default_pvid.is_some() && des_default_pvid != cur_default_pvid
    }
}
