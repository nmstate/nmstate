// SPDX-License-Identifier: Apache-2.0

use crate::{HsrInterface, HsrProtocol, nm::nm_dbus::NmConnection};

pub(crate) fn gen_nm_hsr_setting(
    iface: &HsrInterface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_hsr_set = nm_conn.hsr.as_ref().cloned().unwrap_or_default();
    if let Some(hsr_conf) = iface.hsr.as_ref() {
        nm_hsr_set.port1 = Some(hsr_conf.port1.clone());
        nm_hsr_set.port2 = Some(hsr_conf.port2.clone());
        nm_hsr_set.multicast_spec = Some(hsr_conf.multicast_spec as u32);
        nm_hsr_set.prp = match hsr_conf.protocol {
            HsrProtocol::Prp => Some(true),
            HsrProtocol::Hsr | HsrProtocol::Hsr2012 => Some(false),
        };
        nm_hsr_set.protocol_version = match hsr_conf.protocol {
            // TODO: If protocol is hsr-2010, don't set protocol version
            // for backwards compatibility. This can be updated when the
            // minimum required version of NetworkManager is 1.56.
            HsrProtocol::Hsr => None,
            HsrProtocol::Hsr2012 => Some(1),
            HsrProtocol::Prp => None,
        };
    }
    nm_conn.hsr = Some(nm_hsr_set);
}
