// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use super::nm_dbus::{NmActiveConnection, NmIfaceType};

pub(crate) fn create_index_for_nm_acs_by_name_type(
    nm_acs: &[NmActiveConnection],
) -> HashMap<(&str, NmIfaceType), &NmActiveConnection> {
    let mut ret = HashMap::new();
    for nm_ac in nm_acs {
        let nm_iface_type = match &nm_ac.iface_type {
            NmIfaceType::Veth => NmIfaceType::Ethernet,
            t => t.clone(),
        };
        ret.insert((nm_ac.iface_name.as_str(), nm_iface_type), nm_ac);
    }
    ret
}
