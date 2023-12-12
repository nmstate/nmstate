// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{NmConnection, NmSettingVlanFlag};

use crate::{VlanInterface, VlanProtocol, VlanRegistrationProtocol};

const NM_802_1_AD: &str = "802.1ad";
const NM_802_1_Q: &str = "802.1Q";

pub(crate) fn gen_nm_vlan_setting(
    iface: &VlanInterface,
    nm_conn: &mut NmConnection,
) {
    if let Some(vlan_conf) = iface.vlan.as_ref() {
        let mut nm_vlan = nm_conn.vlan.as_ref().cloned().unwrap_or_default();
        nm_vlan.id = Some(vlan_conf.id.into());
        nm_vlan.parent = Some(vlan_conf.base_iface.clone());
        if let Some(protocol) = vlan_conf.protocol {
            match protocol {
                VlanProtocol::Ieee8021Ad => {
                    nm_vlan.protocol = Some(NM_802_1_AD.to_string());
                }
                VlanProtocol::Ieee8021Q => {
                    // To support old NetworkManager 1.41- which VLAN protocol
                    // is not supported, we only set 802.1q protocol explicitly
                    // when protocol is already defined in NM connection.
                    if nm_vlan.protocol.is_some() {
                        nm_vlan.protocol = Some(NM_802_1_Q.to_string());
                    }
                }
            }
        }

        if let Some(registration_protocol) = vlan_conf.registration_protocol {
            match registration_protocol {
                VlanRegistrationProtocol::Gvrp => {
                    nm_vlan
                        .flags
                        .retain(|x| !matches!(x, NmSettingVlanFlag::Mvrp));
                    nm_vlan.flags.push(NmSettingVlanFlag::Gvrp);
                }
                VlanRegistrationProtocol::Mvrp => {
                    nm_vlan
                        .flags
                        .retain(|x| !matches!(x, NmSettingVlanFlag::Gvrp));
                    nm_vlan.flags.push(NmSettingVlanFlag::Mvrp);
                }
                VlanRegistrationProtocol::None => {
                    nm_vlan.flags.retain(|x| {
                        !matches!(
                            x,
                            NmSettingVlanFlag::Gvrp | NmSettingVlanFlag::Mvrp,
                        )
                    });
                }
            }
        }

        if let Some(reorder_headers) = vlan_conf.reorder_headers {
            if reorder_headers {
                nm_vlan.flags.push(NmSettingVlanFlag::ReorderHeaders);
            } else {
                nm_vlan.flags.retain(|x| {
                    !matches!(x, NmSettingVlanFlag::ReorderHeaders)
                });
            }
        }

        if let Some(loose_binding) = vlan_conf.loose_binding {
            if loose_binding {
                nm_vlan.flags.push(NmSettingVlanFlag::LooseBinding);
            } else {
                nm_vlan
                    .flags
                    .retain(|x| !matches!(x, NmSettingVlanFlag::LooseBinding));
            }
        }
        nm_conn.vlan = Some(nm_vlan);
    }
}
