// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use super::{
    super::{NmConnection, NmError, NmSettingConnection, ToKeyfile},
    keyfile::keyfile_sections_to_string,
};

impl ToKeyfile for NmSettingConnection {}

impl NmConnection {
    pub fn to_keyfile(&self) -> Result<String, NmError> {
        let mut sections: Vec<(&str, HashMap<String, zvariant::Value>)> =
            Vec::new();
        if let Some(con_set) = &self.connection {
            sections.push(("connection", con_set.to_keyfile()?));
        }
        if let Some(bond_set) = &self.bond {
            sections.push(("bond", bond_set.to_keyfile()?));
        }
        if let Some(bond_port_set) = &self.bond_port {
            sections.push(("bond-port", bond_port_set.to_keyfile()?));
        }
        if let Some(br_set) = &self.bridge {
            sections.push(("bridge", br_set.to_keyfile()?));
        }
        if let Some(br_port_set) = &self.bridge_port {
            sections.push(("bridge-port", br_port_set.to_keyfile()?));
        }
        if let Some(ipv4_set) = &self.ipv4 {
            sections.push(("ipv4", ipv4_set.to_keyfile()?));
        }
        if let Some(ipv6_set) = &self.ipv6 {
            sections.push(("ipv6", ipv6_set.to_keyfile()?));
        }
        if let Some(ovs_bridge_set) = &self.ovs_bridge {
            sections.push(("ovs-bridge", ovs_bridge_set.to_keyfile()?));
        }
        if let Some(ovs_port_set) = &self.ovs_port {
            sections.push(("ovs-port", ovs_port_set.to_keyfile()?));
        }
        if let Some(ovs_iface_set) = &self.ovs_iface {
            sections.push(("ovs-interface", ovs_iface_set.to_keyfile()?));
        }
        if let Some(ovs_patch_set) = &self.ovs_patch {
            sections.push(("ovs-patch", ovs_patch_set.to_keyfile()?));
        }
        if let Some(ovs_dpdk_set) = &self.ovs_dpdk {
            sections.push(("ovs-dpdk", ovs_dpdk_set.to_keyfile()?));
        }
        if let Some(wired_set) = &self.wired {
            sections.push(("ethernet", wired_set.to_keyfile()?));
        }
        if let Some(vlan) = &self.vlan {
            sections.push(("vlan", vlan.to_keyfile()?));
        }
        if let Some(vxlan) = &self.vxlan {
            sections.push(("vxlan", vxlan.to_keyfile()?));
        }
        if let Some(sriov) = &self.sriov {
            sections.push(("sriov", sriov.to_keyfile()?));
        }
        if let Some(mac_vlan) = &self.mac_vlan {
            sections.push(("macvlan", mac_vlan.to_keyfile()?));
        }
        if let Some(vrf) = &self.vrf {
            sections.push(("vrf", vrf.to_keyfile()?));
        }
        if let Some(veth) = &self.veth {
            sections.push(("veth", veth.to_keyfile()?));
        }
        if let Some(user) = &self.user {
            sections.push(("user", user.to_keyfile()?));
        }
        if let Some(ieee8021x) = &self.ieee8021x {
            sections.push(("802-1x", ieee8021x.to_keyfile()?));
        }
        if let Some(ethtool) = &self.ethtool {
            sections.push(("ethtool", ethtool.to_keyfile()?));
        }
        if let Some(ib) = &self.infiniband {
            sections.push(("infiniband", ib.to_keyfile()?));
        }
        if let Some(ovs_eids) = &self.ovs_ext_ids {
            sections.push(("ovs-external-ids", ovs_eids.to_keyfile()?));
        }
        if let Some(ovs_other_cfgs) = &self.ovs_other_config {
            sections.push(("ovs-other-config", ovs_other_cfgs.to_keyfile()?));
        }
        if let Some(vpn_cfg) = &self.vpn {
            sections.push(("vpn", vpn_cfg.to_keyfile()?));
            if let Some(s) = vpn_cfg.secrets_to_keyfile() {
                sections.push(("vpn-secrets", s));
            }
        }
        if let Some(generic_cfg) = &self.generic {
            sections.push(("generic", generic_cfg.to_keyfile()?));
        }

        keyfile_sections_to_string(&sections)
    }
}
