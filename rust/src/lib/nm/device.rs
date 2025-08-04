// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::nm::nm_dbus::NmDevice;
use crate::InterfaceType;

pub(crate) fn create_index_for_nm_devs(
    nm_devs: &[NmDevice],
) -> HashMap<(&str, InterfaceType), &NmDevice> {
    let mut ret = HashMap::new();
    for nm_dev in nm_devs {
        ret.insert(
            (
                nm_dev.name.as_str(),
                InterfaceType::from(&nm_dev.iface_type),
            ),
            nm_dev,
        );
    }
    ret
}
