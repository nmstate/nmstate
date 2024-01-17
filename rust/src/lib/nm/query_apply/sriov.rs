// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use serde::Deserialize;

use crate::{ErrorKind, Interface, MergedNetworkState, NmstateError};

const OCP_SRIOV_OPERATOR_CFG_DIR: &str = "/etc/sriov-operator/pci";

pub(crate) fn check_sriov_operator_overlap(
    state: &MergedNetworkState,
) -> Result<(), NmstateError> {
    let mut pf_list: HashSet<String> = HashSet::new();
    for iface in state.interfaces.kernel_ifaces.values().filter_map(|i| {
        if let Some(Interface::Ethernet(eth_iface)) = i.for_apply.as_ref() {
            Some(eth_iface)
        } else {
            None
        }
    }) {
        if iface
            .ethernet
            .as_ref()
            .and_then(|e| e.sr_iov.as_ref())
            .is_some()
        {
            pf_list.insert(iface.base.name.to_string());
        }
    }

    let ex_pf_list = get_ocp_sriov_provider_pf_list();

    let overlap_pfs: Vec<&str> = pf_list
        .intersection(&ex_pf_list)
        .map(String::as_str)
        .collect();

    if !overlap_pfs.is_empty() {
        if state.apply_options.allow_overlap_ext_sriov {
            log::warn!(
                "Found OpenShift SRIOV-network operator also \
                controlling PF interfaces in desired state: {}",
                overlap_pfs.join(",")
            );
        } else {
            return Err(NmstateError::new(
                ErrorKind::SrIovOperatorOverlap,
                format!(
                    "Found OpenShift SRIOV-network operator also \
                    controlling PF interfaces in desired state: {}, \
                    you may pass `--allow-sriov-overlap` to nmstatectl or \
                    call `NetworkState.set_allow_overlap_ext_sriov()`",
                    overlap_pfs.join(",")
                ),
            ));
        }
    }
    Ok(())
}

fn get_ocp_sriov_provider_pf_list() -> HashSet<String> {
    let mut ret: HashSet<String> = HashSet::new();

    if let Ok(fd) = std::fs::read_dir(OCP_SRIOV_OPERATOR_CFG_DIR) {
        for dir in fd {
            if let Some(pf) = dir.ok().and_then(|d| get_ocp_pf_name(&d)) {
                ret.insert(pf);
            }
        }
    }
    ret
}

#[derive(Deserialize, Debug, Clone, Default, PartialEq, Eq)]
struct OcpSriovConf {
    #[serde(rename = "numVfs")]
    num_vfs: u32,
    name: String,
}

fn get_ocp_pf_name(dir: &std::fs::DirEntry) -> Option<String> {
    let file_path =
        std::path::Path::new(OCP_SRIOV_OPERATOR_CFG_DIR).join(dir.path());

    std::fs::File::open(file_path)
        .ok()
        .and_then(|fd| {
            serde_json::from_reader::<std::fs::File, OcpSriovConf>(fd).ok()
        })
        .map(|c| c.name)
}
