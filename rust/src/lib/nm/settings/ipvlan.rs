// SPDX-License-Identifier: Apache-2.0

use crate::nm::nm_dbus::NmConnection;

use crate::{IpVlanInterface, IpVlanMode};

pub(crate) fn gen_nm_ipvlan_setting(
    iface: &IpVlanInterface,
    nm_conn: &mut NmConnection,
) {
    let mut nm_ipvlan_set =
        nm_conn.ipvlan.as_ref().cloned().unwrap_or_default();
    if let Some(ipvlan_conf) = iface.ipvlan.as_ref() {
        nm_ipvlan_set.parent = ipvlan_conf.base_iface.clone();
        nm_ipvlan_set.mode = match ipvlan_conf.mode {
            Some(v) => Some(v.into()),
            None => Some(IpVlanMode::default().into()),
        };
        nm_ipvlan_set.private = ipvlan_conf.private;
        nm_ipvlan_set.vepa = ipvlan_conf.vepa;
    }
    nm_conn.ipvlan = Some(nm_ipvlan_set);
}
