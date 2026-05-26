// SPDX-License-Identifier: Apache-2.0

use std::fs;

use crate::{
    ErrorKind, Interface, InterfaceType, MergedInterfaces, NmstateError,
};

fn write_sysfs_bool(
    iface_name: &str,
    subpath: &str,
    value: bool,
) -> Result<(), NmstateError> {
    let path =
        format!("/sys/class/net/{iface_name}/{subpath}");
    let val_str = if value { "1" } else { "0" };
    fs::write(&path, val_str).map_err(|e| {
        NmstateError::new(
            ErrorKind::PluginFailure,
            format!("Failed to write {val_str} to {path}: {e}"),
        )
    })
}

pub(crate) fn apply_vnicc_conf(
    merged_ifaces: &MergedInterfaces,
) -> Result<(), NmstateError> {
    for merged_iface in merged_ifaces.kernel_ifaces.values().filter(|i| {
        i.is_changed()
            && i.merged.iface_type() == InterfaceType::Ethernet
            && i.merged.is_up()
    }) {
        if let Interface::Ethernet(eth_iface) = &merged_iface.merged
            && let Some(eth_conf) = eth_iface.ethernet.as_ref()
            && let Some(vnicc) = eth_conf.vnicc.as_ref()
        {
            let iface_name = eth_iface.base.name.as_str();
            if let Some(bridge_invisible) = vnicc.bridge_invisible {
                write_sysfs_bool(
                    iface_name,
                    "vnicc/bridge_invisible",
                    bridge_invisible,
                )?;
            }
            if let Some(learning) = vnicc.learning {
                write_sysfs_bool(iface_name, "vnicc/learning", learning)?;
            }
        }
    }
    Ok(())
}
