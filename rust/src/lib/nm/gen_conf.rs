// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, MergedNetworkState, NmstateError};

use super::{
    dns::{store_dns_config_to_iface, store_dns_search_or_option_to_iface},
    profile::perpare_nm_conns,
    route::store_route_config,
    route_rule::store_route_rule_config,
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
            "Cannot store hostname configuration to keyfile \
            of NetworkManager, please edit /etc/hostname manually"
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

    let nm_conns = perpare_nm_conns(
        &merged_state,
        &Vec::new(),
        &Vec::new(),
        true, // MPTCP support enabled
        true, // gen_conf mode
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
