// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, InterfaceIdentifier, MergedInterfaces, MergedNetworkState,
    NmstateError,
};

use super::{
    connection::prepare_nm_conns,
    dns::{store_dns_config_to_iface, store_dns_search_or_option_to_iface},
    route::store_route_config,
    route_rule::store_route_rule_config,
    settings::uuid_from_name_and_type,
    NmConnectionMatcher,
};

pub(crate) fn nm_gen_conf(
    merged_state: &MergedNetworkState,
) -> Result<Vec<(String, String)>, NmstateError> {
    if merged_state
        .hostname
        .desired
        .as_ref()
        .and_then(|c| c.config.as_ref())
        .is_some()
    {
        log::warn!(
            "Cannot store hostname configuration to keyfile of \
             NetworkManager, please edit /etc/hostname manually"
        );
    }

    let mut merged_state = merged_state.clone();
    store_route_config(&mut merged_state)?;
    store_route_rule_config(&mut merged_state)?;
    if merged_state.dns.is_search_or_option_only() {
        store_dns_search_or_option_to_iface(&mut merged_state, &[], &[])?;
    } else {
        store_dns_config_to_iface(&mut merged_state, &[], &[])?;
    }

    // If parent interface is not referenced by interface name, in `gen_conf`
    // mode, nmstate cannot tell the real interface name of parent, so child
    // should refer its parent by UUID.
    // Since we are using `stable_uuid` in gen_conf mode, we can predict the
    // UUID via `uuid_from_name_and_type()` of parent.
    use_uuid_for_non_name_ref_parent(&mut merged_state.interfaces);

    let conn_matcher = NmConnectionMatcher::new(
        Vec::new(),
        Vec::new(),
        Vec::new(),
        &merged_state.interfaces,
    );

    let nm_conns = prepare_nm_conns(
        &merged_state,
        &conn_matcher,
        &[],
        true,  // gen_conf mode
        false, // is_retry
    )?
    .to_store;

    let mut ret = Vec::new();
    for nm_conn in nm_conns {
        match nm_conn.to_keyfile() {
            Ok(s) => {
                if let Some(id) = nm_conn.id() {
                    ret.push((format!("{id}.nmconnection"), s));
                }
            }
            Err(e) => {
                return Err(NmstateError::new(
                    ErrorKind::PluginFailure,
                    format!(
                        "Bug in NM plugin, failed to generate configure: {e}"
                    ),
                ));
            }
        }
    }
    Ok(ret)
}

// If parent interface is not referenced by interface name, in `gen_conf`
// mode, nmstate cannot tell the real interface name of parent, so child should
// refer its parent by UUID.
fn use_uuid_for_non_name_ref_parent(merged_ifaces: &mut MergedInterfaces) {
    // Pending changes holds Vec of (child_interface_name, parent_uuid).
    let mut pending_changes: Vec<(String, String)> = Vec::new();
    for iface in merged_ifaces
        .kernel_ifaces
        .values()
        .filter_map(|i| i.for_apply.as_ref())
    {
        if let Some(parent) = iface.parent() {
            if let Some(parent_iface) = merged_ifaces.kernel_ifaces.get(parent)
            {
                if parent_iface.merged.base_iface().identifier
                    != Some(InterfaceIdentifier::Name)
                    && parent_iface.merged.base_iface().identifier.is_some()
                {
                    let parent_uuid = uuid_from_name_and_type(
                        parent_iface.merged.name(),
                        &parent_iface.merged.iface_type(),
                    );
                    pending_changes
                        .push((iface.name().to_string(), parent_uuid));
                }
            }
        }
    }
    for (child_name, parent_uuid) in pending_changes {
        if let Some(child_iface) = merged_ifaces
            .kernel_ifaces
            .get_mut(&child_name)
            .and_then(|i| i.for_apply.as_mut())
        {
            child_iface.change_parent_name(&parent_uuid);
        }
    }
}
