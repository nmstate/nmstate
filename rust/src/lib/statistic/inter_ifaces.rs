// SPDX-License-Identifier: Apache-2.0

use crate::{InterfaceType, MergedInterface, MergedInterfaces};

impl MergedInterfaces {
    pub(crate) fn gen_topoligies(&self) -> Vec<String> {
        let mut ret = Vec::new();
        for iface in self
            .kernel_ifaces
            .values()
            .chain(self.user_ifaces.values())
            .filter(|i| i.merged.is_up() && (i.is_desired() || i.is_changed()))
        {
            let new_top = self.get_topoligy(iface).join(" -> ").to_string();
            if !ret.contains(&new_top) {
                ret.push(new_top);
            }
        }
        let mut dups = Vec::new();
        ret.sort_unstable_by_key(|t| t.len());
        for (i, top) in ret.iter().enumerate() {
            if ret[i + 1..].iter().any(|t| t.contains(top.as_str())) {
                dups.push(top.clone());
            }
        }
        ret.retain(|t| !dups.contains(t));

        ret
    }

    fn get_topoligy(&self, iface: &MergedInterface) -> Vec<String> {
        let mut ret = self.get_superior_types(iface);
        ret.push(iface.merged.iface_type().to_string());
        ret.append(&mut self.get_subordinate_types(iface));
        ret
    }

    fn get_superior_types(&self, iface: &MergedInterface) -> Vec<String> {
        let mut ret: Vec<String> = Vec::new();
        if iface.merged.iface_type() == InterfaceType::OvsInterface {
            if let Some(i) = iface.get_ip_topology() {
                ret.push(i);
            }
        } else if let (Some(ctrl_name), Some(ctrl_type)) = (
            iface.merged.base_iface().controller.as_ref(),
            iface.merged.base_iface().controller_type.as_ref(),
        ) {
            if let Some(ctrl_iface) =
                self.get_iface(ctrl_name, ctrl_type.clone())
            {
                ret.append(&mut self.get_superior_types(ctrl_iface));
                ret.push(ctrl_type.to_string());
            }
        } else if let Some(i) = iface.get_ip_topology() {
            ret.push(i);
        }
        ret
    }

    // To build up the topology, we are considering the vlan parent as
    // an subordinate of VLAN.
    fn get_subordinate_types(&self, iface: &MergedInterface) -> Vec<String> {
        let mut ret: Vec<String> = Vec::new();
        if let Some(parent) = iface.merged.parent() {
            let parent_iface =
                if iface.merged.iface_type() == InterfaceType::OvsInterface {
                    self.get_iface(parent, InterfaceType::OvsBridge)
                } else {
                    self.kernel_ifaces.get(parent)
                };
            if let Some(parent_iface) = parent_iface {
                ret.push(parent_iface.merged.iface_type().to_string());
                ret.append(&mut self.get_subordinate_types(parent_iface));
            }
        } else if let Some(ports) = iface.merged.ports() {
            // for all the ports, we took the one holding the most complex
            // topology.
            let mut most_complex_top = Vec::new();

            // TODO: We do not support showing ovs-bond yet.
            for port in ports {
                if let Some(port_iface) =
                    self.kernel_ifaces.get(&port.to_string())
                {
                    if port_iface.merged.iface_type()
                        == InterfaceType::OvsInterface
                    {
                        continue;
                    }
                    let mut port_subs =
                        vec![port_iface.merged.iface_type().to_string()];
                    port_subs
                        .append(&mut self.get_subordinate_types(port_iface));
                    if port_subs.len() > most_complex_top.len() {
                        most_complex_top = port_subs;
                    }
                }
            }
            ret.append(&mut most_complex_top);
        }
        ret
    }
}
