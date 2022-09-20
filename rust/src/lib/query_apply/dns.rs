// SPDX-License-Identifier: Apache-2.0

use std::net::{Ipv4Addr, Ipv6Addr};

use crate::{ip::is_ipv6_addr, DnsState, ErrorKind, NmstateError};

impl DnsState {
    pub(crate) fn verify(&self, current: &Self) -> Result<(), NmstateError> {
        if let Some(conf) = self.config.as_ref() {
            if let Some(srvs) = conf.server.as_ref() {
                let cur_conf = current.config.as_ref().ok_or_else(|| {
                    // Do not log verification error as we have fail-retry
                    NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Failed to apply DNS config: desire {:?} got {:?}",
                            self, current
                        ),
                    )
                })?;
                let mut canonicalized_srvs = Vec::new();
                for srv in srvs {
                    if is_ipv6_addr(srv) {
                        if let Ok(ip_addr) = srv.parse::<Ipv6Addr>() {
                            canonicalized_srvs.push(ip_addr.to_string());
                        }
                    } else if let Ok(ip_addr) = srv.parse::<Ipv4Addr>() {
                        canonicalized_srvs.push(ip_addr.to_string());
                    }
                }

                if cur_conf.server != Some(canonicalized_srvs)
                    && !(cur_conf.server.is_none() && srvs.is_empty())
                {
                    return Err(NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Failed to apply DNS config: desire name servers \
                            {:?}, got {:?}",
                            srvs,
                            cur_conf.server.as_ref()
                        ),
                    ));
                }
            }
            if let Some(schs) = conf.search.as_ref() {
                let cur_conf = current.config.as_ref().ok_or_else(|| {
                    NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Failed to apply DNS config: desire {:?} got {:?}",
                            self, current
                        ),
                    )
                })?;
                if cur_conf.search != Some(schs.to_vec())
                    && !(cur_conf.search.is_none() && schs.is_empty())
                {
                    return Err(NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Failed to apply DNS config: desire searches \
                            {:?}, got {:?}",
                            schs,
                            cur_conf.search.as_ref()
                        ),
                    ));
                }
            }
        }
        Ok(())
    }
}
