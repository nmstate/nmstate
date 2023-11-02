// SPDX-License-Identifier: Apache-2.0

use crate::{Interface, Interfaces, NetworkState, NmstateError};

use super::json::{search_item, update_items};

pub(crate) fn get_iface_match(
    prop_path: &[String],
    value: &str,
    state: &NetworkState,
    line: &str,
    pos: usize,
) -> Result<Interfaces, NmstateError> {
    let mut ret = Interfaces::new();
    for iface in search_item(
        "interface",
        prop_path,
        value,
        state.interfaces.to_vec().as_slice(),
        line,
        pos,
    )? {
        ret.push(iface.clone());
    }

    Ok(ret)
}

pub(crate) fn update_ifaces(
    prop_path: &[String],
    value: Option<&str>,
    state: &NetworkState,
    line: &str,
    pos: usize,
) -> Result<Interfaces, NmstateError> {
    let ifaces: Vec<Interface> = state
        .interfaces
        .to_vec()
        .as_slice()
        .iter()
        .cloned()
        .cloned()
        .collect();

    let mut ret = Interfaces::new();
    for iface in
        update_items("interface", prop_path, value, &ifaces, line, pos)?
    {
        ret.push(iface);
    }
    Ok(ret)
}
