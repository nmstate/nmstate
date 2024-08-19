// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::nm::nm_dbus::{NmDevice, NmIfaceType};

pub(crate) fn create_index_for_nm_devs(
    nm_devs: &[NmDevice],
) -> HashMap<(String, NmIfaceType), &NmDevice> {
    let mut ret: HashMap<(String, NmIfaceType), &NmDevice> = HashMap::new();
    for nm_dev in nm_devs {
        ret.insert(
            (nm_dev.name.to_string(), nm_dev.iface_type.clone()),
            nm_dev,
        );
    }
    ret
}
