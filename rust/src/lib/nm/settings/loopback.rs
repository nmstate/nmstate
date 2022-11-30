// SPDX-License-Identifier: Apache-2.0

use crate::nm::nm_dbus::NmConnection;

use crate::LoopbackInterface;

pub(crate) fn gen_nm_loopback_setting(
    iface: &LoopbackInterface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_lo_set = nm_conn.loopback.as_ref().cloned().unwrap_or_default();
    if let Some(mtu) = iface.base.mtu {
        nm_lo_set.mtu = Some(mtu as u32);
    }
    nm_conn.loopback = Some(nm_lo_set)
}
