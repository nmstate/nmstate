// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{
    nm::settings::{
        iface_to_nm_connections, use_uuid_for_controller_reference,
        use_uuid_for_parent_reference,
    },
    ErrorKind, Interface, NetworkState, NmstateError,
};

pub(crate) fn nm_gen_conf(
    net_state: &NetworkState,
) -> Result<Vec<(String, String)>, NmstateError> {
    let mut nm_conns = Vec::new();
    if net_state
        .hostname
        .as_ref()
        .and_then(|c| c.config.as_ref())
        .is_some()
    {
        log::warn!(
            "Cannot store hostname configuration to keyfile \
            of NetworkManager, please edit /etc/hostname manually"
        );
    }
    let ifaces = net_state.interfaces.to_vec();
    for iface in &ifaces {
        if iface.is_absent() {
            log::warn!("ignoring iface {} because is absent", iface.name(),);
            continue;
        }
        let mut ctrl_iface: Option<&Interface> = None;
        if let Some(ctrl_iface_name) = &iface.base_iface().controller {
            if let Some(ctrl_type) = &iface.base_iface().controller_type {
                ctrl_iface = net_state
                    .interfaces
                    .get_iface(ctrl_iface_name, ctrl_type.clone());
            }
        }

        for mut nm_conn in iface_to_nm_connections(
            iface,
            ctrl_iface,
            &[],
            &[],
            false,
            &NetworkState::new(),
        )? {
            if iface.is_down() {
                if let Some(nm_conn_set) = nm_conn.connection.as_mut() {
                    nm_conn_set.autoconnect = Some(false);
                }
            }
            nm_conns.push(nm_conn);
        }
    }

    use_uuid_for_controller_reference(
        &mut nm_conns,
        &net_state.interfaces.user_ifaces,
        &HashMap::new(),
        &[],
    )?;

    use_uuid_for_parent_reference(
        &mut nm_conns,
        &net_state.interfaces.kernel_ifaces,
        &[],
    );

    let mut ret = Vec::new();
    for nm_conn in nm_conns {
        match nm_conn.to_keyfile() {
            Ok(s) => {
                if let Some(id) = nm_conn.id() {
                    ret.push((format!("{}.nmconnection", id), s));
                }
            }
            Err(e) => {
                return Err(NmstateError::new(
                    ErrorKind::PluginFailure,
                    format!(
                        "Bug in NM plugin, failed to generate configure: {}",
                        e
                    ),
                ));
            }
        }
    }
    Ok(ret)
}
