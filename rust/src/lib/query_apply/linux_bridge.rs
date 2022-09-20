// SPDX-License-Identifier: Apache-2.0

use crate::{BridgePortVlanConfig, LinuxBridgeConfig, LinuxBridgeInterface};

impl LinuxBridgeInterface {
    pub(crate) const INTEGER_ROUNDED_OPTIONS: [&'static str; 5] = [
        "interface.bridge.options.multicast-last-member-interval",
        "interface.bridge.options.multicast-membership-interval",
        "interface.bridge.options.multicast-querier-interval",
        "interface.bridge.options.multicast-query-response-interval",
        "interface.bridge.options.multicast-startup-query-interval",
    ];

    pub(crate) fn update_bridge(&mut self, other: &LinuxBridgeInterface) {
        if let Some(br_conf) = &mut self.bridge {
            br_conf.update(other.bridge.as_ref());
        } else {
            self.bridge = other.bridge.clone();
        }
    }

    pub(crate) fn pre_verify_cleanup(&mut self) {
        self.sort_ports();
        self.use_upper_case_of_mac_address();
        self.flatten_port_vlan_ranges();
        self.sort_port_vlans();
        self.treat_none_vlan_as_empty_dict();
        self.remove_runtime_only_timers();
    }

    fn remove_runtime_only_timers(&mut self) {
        if let Some(ref mut br_conf) = self.bridge {
            if let Some(ref mut opts) = &mut br_conf.options {
                opts.gc_timer = None;
                opts.hello_timer = None;
            }
        }
    }

    fn sort_ports(&mut self) {
        if let Some(ref mut br_conf) = self.bridge {
            if let Some(ref mut port_confs) = &mut br_conf.port {
                port_confs.sort_unstable_by_key(|p| p.name.clone())
            }
        }
    }

    fn use_upper_case_of_mac_address(&mut self) {
        if let Some(address) = self
            .bridge
            .as_mut()
            .and_then(|br_conf| br_conf.options.as_mut())
            .and_then(|br_opts| br_opts.group_addr.as_mut())
        {
            address.make_ascii_uppercase()
        }
    }

    fn flatten_port_vlan_ranges(&mut self) {
        if let Some(port_confs) = self
            .bridge
            .as_mut()
            .and_then(|br_conf| br_conf.port.as_mut())
        {
            for port_conf in port_confs {
                port_conf
                    .vlan
                    .as_mut()
                    .map(BridgePortVlanConfig::flatten_vlan_ranges);
            }
        }
    }

    fn sort_port_vlans(&mut self) {
        if let Some(port_confs) = self
            .bridge
            .as_mut()
            .and_then(|br_conf| br_conf.port.as_mut())
        {
            for port_conf in port_confs {
                port_conf
                    .vlan
                    .as_mut()
                    .map(BridgePortVlanConfig::sort_trunk_tags);
            }
        }
    }

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

    pub(crate) fn remove_port(&mut self, port_name: &str) {
        if let Some(index) = self.bridge.as_ref().and_then(|br_conf| {
            br_conf.port.as_ref().and_then(|port_confs| {
                port_confs
                    .iter()
                    .position(|port_conf| port_conf.name == port_name)
            })
        }) {
            self.bridge
                .as_mut()
                .and_then(|br_conf| br_conf.port.as_mut())
                .map(|port_confs| port_confs.remove(index));
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
            self.options = other.options.clone();
            self.port = other.port.clone();
        }
    }
}
