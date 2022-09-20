// SPDX-License-Identifier: Apache-2.0

// The document string for MptcpAddressFlag is copy from manpage of
// `IP-MPTCP(8)` which is licensed under GPLv2.0+

use serde::{Deserialize, Serialize};

use crate::{BaseInterface, ErrorKind, NmstateError};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct MptcpConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Automatically assign MPTCP flags to all valid IP addresses of this
    /// interface including both static and dynamic ones.
    pub address_flags: Option<Vec<MptcpAddressFlag>>,
}

#[derive(
    Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize,
)]
#[serde(rename_all = "kebab-case")]
#[non_exhaustive]
pub enum MptcpAddressFlag {
    /// The endpoint will be announced/signaled to each peer via an MPTCP
    /// ADD_ADDR sub-option. Upon reception of an ADD_ADDR sub-option, the
    /// peer can try to create additional subflows. Cannot used along with
    /// MptcpAddressFlag::Fullmesh as Linux kernel enforced.
    Signal,
    /// If additional subflow creation is allowed by the MPTCP limits, the
    /// MPTCP path manager will try to create an additional subflow using
    /// this endpoint as the source address after the MPTCP connection is
    /// established.
    Subflow,
    /// If this is a subflow endpoint, the subflows created using this endpoint
    /// will have the backup flag set during the connection process. This flag
    /// instructs the peer to only send data on a given subflow when all
    /// non-backup subflows are unavailable. This does not affect outgoing
    /// data, where subflow priority is determined by the backup/non-backup
    /// flag received from the peer.
    Backup,
    /// If this is a subflow endpoint and additional subflow creation is
    /// allowed by the MPTCP limits, the MPTCP path manager will try to
    /// create an additional subflow for each known peer address, using
    /// this endpoint as the source address. This will occur after the
    /// MPTCP connection is established. If the peer did not announce any
    /// additional addresses using the MPTCP ADD_ADDR sub-option, this will
    /// behave the same as a plain subflow endpoint.  When the peer does
    /// announce addresses, each received ADD_ADDR sub-option will trigger
    /// creation of an additional subflow to generate a full mesh topology.
    Fullmesh,
}

pub(crate) fn mptcp_pre_edit_cleanup(iface: &mut BaseInterface) {
    remove_per_addr_mptcp_flags(iface);
}

pub(crate) fn validate_mptcp(
    iface: &BaseInterface,
) -> Result<(), NmstateError> {
    if let Some(iface_flags) =
        iface.mptcp.as_ref().and_then(|m| m.address_flags.as_ref())
    {
        if iface_flags.contains(&MptcpAddressFlag::Signal)
            && iface_flags.contains(&MptcpAddressFlag::Fullmesh)
        {
            let e = NmstateError::new(
                ErrorKind::InvalidArgument,
                "MPTCP flags mustn't have both signal and fullmesh".to_string(),
            );
            log::error!("{}", e);
            return Err(e);
        }
    }
    validate_iface_mptcp_and_addr_mptcp_flags(iface);

    Ok(())
}

fn validate_iface_mptcp_and_addr_mptcp_flags(iface: &BaseInterface) {
    let mut iface_flags =
        match iface.mptcp.as_ref().and_then(|m| m.address_flags.as_ref()) {
            Some(f) => f.clone(),
            None => Vec::new(),
        };
    iface_flags.sort_unstable();

    let empty_ip_addrs = Vec::new();

    for ip_addr in iface
        .ipv4
        .as_ref()
        .and_then(|i| i.addresses.as_ref())
        .unwrap_or(&empty_ip_addrs)
        .iter()
        .chain(
            iface
                .ipv6
                .as_ref()
                .and_then(|i| i.addresses.as_ref())
                .unwrap_or(&empty_ip_addrs)
                .iter(),
        )
    {
        if let Some(mut addr_flags) = ip_addr.mptcp_flags.as_ref().cloned() {
            addr_flags.sort_unstable();
            if iface_flags != addr_flags {
                log::warn!(
                    "Nmstate does not support setting different MPTCP flags \
                    within the interface. Ignoring MPTCP flags {:?} of IP \
                    address {}/{} as it is different from interface level \
                    MPTCP flags {:?}",
                    addr_flags,
                    ip_addr.ip,
                    ip_addr.prefix_length,
                    iface_flags
                );
            }
        }
    }
}

pub(crate) fn remove_per_addr_mptcp_flags(iface: &mut BaseInterface) {
    let mut empty_ipv4_addrs = Vec::new();
    let mut empty_ipv6_addrs = Vec::new();

    for ip_addr in iface
        .ipv4
        .as_mut()
        .and_then(|i| i.addresses.as_mut())
        .unwrap_or(&mut empty_ipv4_addrs)
        .iter_mut()
        .chain(
            iface
                .ipv6
                .as_mut()
                .and_then(|i| i.addresses.as_mut())
                .unwrap_or(&mut empty_ipv6_addrs)
                .iter_mut(),
        )
    {
        ip_addr.mptcp_flags = None;
    }
}
