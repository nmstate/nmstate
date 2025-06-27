// SPDX-License-Identifier: Apache-2.0

use super::super::nm_dbus::{NmConnection, NmSettingMatch};
use crate::{BaseInterface, InterfaceIdentifier};

pub(crate) fn apply_iface_match(
    nm_conn: &mut NmConnection,
    base_iface: &BaseInterface,
) {
    match base_iface.identifier.as_ref() {
        Some(InterfaceIdentifier::PciAddress) => {
            if let Some(pci_address) = base_iface.pci_address.as_ref() {
                nm_conn.iface_match = Some(NmSettingMatch {
                    path: Some(vec![format!("pci-{pci_address}")]),
                    ..Default::default()
                });
                if let Some(nm_setting_conn) = nm_conn.connection.as_mut() {
                    nm_setting_conn.iface_name = None;
                }
            }
        }
        Some(InterfaceIdentifier::MacAddress)
        | Some(InterfaceIdentifier::Name) => {
            nm_conn.iface_match = None;
        }
        None => (),
    }
}
