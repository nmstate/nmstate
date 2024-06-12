// SPDX-License-Identifier: Apache-2.0

use std::fmt::Write as _FmtWrite;
use std::io::{Read, Write};
use std::os::unix::fs::OpenOptionsExt;

use crate::{
    DnsClientState, DnsState, ErrorKind, MergedDnsState, NmstateError,
};

const ETC_RESOLV_CONF_PATH: &str = "/etc/resolv.conf";

// When failed to read or parse /etc/resolv.conf, return None
pub(crate) fn get_dns() -> Option<DnsState> {
    let mut content = String::new();
    match std::fs::File::open(ETC_RESOLV_CONF_PATH) {
        Ok(mut fd) => {
            if let Err(e) = fd.read_to_string(&mut content) {
                log::debug!("Failed to read {ETC_RESOLV_CONF_PATH}: {e}");
                return None;
            };
            let mut conf = DnsClientState::default();
            for line in content.split('\n') {
                if let Some(srv) =
                    line.strip_prefix("nameserver ").map(|s| s.trim())
                {
                    if !srv.is_empty() {
                        conf.server
                            .get_or_insert(Vec::new())
                            .push(srv.to_string());
                    }
                }
                if let Some(opts) =
                    line.strip_prefix("options ").map(|s| s.trim())
                {
                    conf.options =
                        Some(opts.split(" ").map(|s| s.to_string()).collect());
                }
                if let Some(searches) =
                    line.strip_prefix("search ").map(|s| s.trim())
                {
                    conf.search = Some(
                        searches.split(" ").map(|s| s.to_string()).collect(),
                    );
                }
            }
            return Some(DnsState {
                running: Some(conf.clone()),
                config: Some(conf),
            });
        }
        Err(e) => {
            log::debug!("Failed to open {ETC_RESOLV_CONF_PATH}: {e}");
        }
    }
    None
}

pub(crate) fn apply_dns_conf_to_etc(
    config: &MergedDnsState,
) -> Result<(), NmstateError> {
    let mut content = String::new();

    if !config.options.is_empty() {
        writeln!(content, "options {}", config.options.as_slice().join(" "))
            .ok();
    }
    if !config.searches.is_empty() {
        writeln!(content, "search {}", config.searches.as_slice().join(" "))
            .ok();
    }

    for srv in config.servers.as_slice() {
        if !srv.is_empty() {
            writeln!(content, "nameserver {}", srv).ok();
        }
    }

    log::info!("Overriding {ETC_RESOLV_CONF_PATH} with:\n{content}");

    match std::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .mode(0o644)
        .open(ETC_RESOLV_CONF_PATH)
    {
        Ok(mut fd) => {
            if let Err(e) = fd.write_all(content.as_bytes()) {
                return Err(NmstateError::new(
                    ErrorKind::Bug,
                    format!(
                        "Failed to apply config to {ETC_RESOLV_CONF_PATH}: {e}"
                    ),
                ));
            }
        }
        Err(e) => {
            return Err(NmstateError::new(
                ErrorKind::Bug,
                format!(
                    "Failed to open {ETC_RESOLV_CONF_PATH} \
                    with write permission: {e}"
                ),
            ));
        }
    }

    Ok(())
}
