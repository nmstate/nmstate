// SPDX-License-Identifier: Apache-2.0

use std::io::Read;

use super::super::nm_dbus::{NmConnection, NmSettingConnection};

use crate::{ErrorKind, MptcpAddressFlag, MptcpConfig, NmstateError};

const NM_MPTCP_FLAG_ALSO_WITHOUT_DEFAULT_ROUTE: u32 = 0x08;
const NM_MPTCP_FLAG_DISABLE: u32 = 0x01;
const NM_MPTCP_FLAG_SIGNAL: u32 = 0x10;
const NM_MPTCP_FLAG_SUBFLOW: u32 = 0x20;
const NM_MPTCP_FLAG_BACKUP: u32 = 0x40;
const NM_MPTCP_FLAG_FULLMESH: u32 = 0x80;

const MPTCP_SYSCTL_PATH: &str = "/proc/sys/net/mptcp/enabled";

pub(crate) fn apply_mptcp_conf(
    nm_conn_set: &mut NmSettingConnection,
    mptcp_conf: &MptcpConfig,
) -> Result<(), NmstateError> {
    if let Some(flags) = mptcp_conf.address_flags.as_ref() {
        if flags.is_empty() {
            nm_conn_set.mptcp_flags = Some(NM_MPTCP_FLAG_DISABLE);
        } else {
            if !is_mptcp_enabled() {
                let e = NmstateError::new(
                    ErrorKind::NotSupportedError,
                    "NetworkManager cannot enable MPTCP via sysctl yet, \
                     please use sysctl to set net.mptcp.enabled as 1 or other \
                     tools before applying MPTCP flags"
                        .to_string(),
                );
                log::error!("{}", e);
                return Err(e);
            }
            let mut nm_mptcp_flags: u32 = 0;
            for flag in flags {
                nm_mptcp_flags |= match flag {
                    MptcpAddressFlag::Signal => NM_MPTCP_FLAG_SIGNAL,
                    MptcpAddressFlag::Subflow => NM_MPTCP_FLAG_SUBFLOW,
                    MptcpAddressFlag::Backup => NM_MPTCP_FLAG_BACKUP,
                    MptcpAddressFlag::Fullmesh => NM_MPTCP_FLAG_FULLMESH,
                }
            }
            if nm_mptcp_flags != 0 {
                // NetworkManager only apply MPTCP flags when default gateway
                // presents. Nmstate do not want to expose that hidden
                // restriction to API, hence we force NM to apply MPTCP flags
                // via NM_MPTCP_FLAG_ALSO_WITHOUT_DEFAULT_ROUTE.
                nm_mptcp_flags |= NM_MPTCP_FLAG_ALSO_WITHOUT_DEFAULT_ROUTE;
            }
            nm_conn_set.mptcp_flags = Some(nm_mptcp_flags);
        }
    }
    Ok(())
}

fn is_mptcp_enabled() -> bool {
    if let Ok(mut fd) = std::fs::File::open(MPTCP_SYSCTL_PATH) {
        let mut content = [0u8; 1];
        if fd.read_exact(&mut content).is_err() {
            false
        } else {
            content[0] == b'1'
        }
    } else {
        false
    }
}

pub(crate) fn remove_nm_mptcp_set(nm_conn: &mut NmConnection) {
    if let Some(nm_conn_set) = nm_conn.connection.as_mut() {
        nm_conn_set.mptcp_flags = None;
    }
}
