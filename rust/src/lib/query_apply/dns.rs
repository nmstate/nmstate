// SPDX-License-Identifier: Apache-2.0

use crate::{DnsState, ErrorKind, MergedDnsState, NmstateError};

impl MergedDnsState {
    pub(crate) fn is_desired(&self) -> bool {
        self.desired.is_some()
    }

    pub(crate) fn is_purge(&self) -> bool {
        self.is_desired()
            && self.servers.is_empty()
            && self.searches.is_empty()
            && self.options.is_empty()
    }

    pub(crate) fn is_changed(&self) -> bool {
        let cur_servers = self
            .current
            .config
            .as_ref()
            .and_then(|c| c.server.clone())
            .unwrap_or_default();
        let cur_searches = self
            .current
            .config
            .as_ref()
            .and_then(|c| c.search.clone())
            .unwrap_or_default();
        let cur_options = self
            .current
            .config
            .as_ref()
            .and_then(|c| c.options.clone())
            .unwrap_or_default();

        self.servers != cur_servers
            || self.searches != cur_searches
            || self.options != cur_options
    }

    pub(crate) fn verify(&self, current: DnsState) -> Result<(), NmstateError> {
        if !self.is_changed() {
            return Ok(());
        }
        let mut current = current.clone();
        current.sanitize().ok();

        let cur_srvs: Vec<String> = current
            .config
            .as_ref()
            .and_then(|c| c.server.as_ref())
            .cloned()
            .unwrap_or_default();
        let cur_schs: Vec<String> = current
            .config
            .as_ref()
            .and_then(|c| c.search.as_ref())
            .cloned()
            .unwrap_or_default();

        let cur_conf = if let Some(c) = current.config.as_ref() {
            c
        } else {
            return Err(NmstateError::new(
                ErrorKind::VerificationError,
                "Current DNS config is empty".to_string(),
            ));
        };

        if cur_srvs != self.servers
            && !(cur_conf.server.is_none() && self.servers.is_empty())
        {
            return Err(NmstateError::new(
                ErrorKind::VerificationError,
                format!(
                    "Failed to apply DNS config: desire name servers '{}', \
                    got '{}'",
                    self.servers.as_slice().join(" "),
                    cur_srvs.as_slice().join(" "),
                ),
            ));
        }

        if cur_schs != self.searches
            && !(cur_conf.search.is_none() && self.searches.is_empty())
        {
            return Err(NmstateError::new(
                ErrorKind::VerificationError,
                format!(
                    "Failed to apply DNS config: desire searches '{}', \
                    got '{}'",
                    self.searches.as_slice().join(" "),
                    cur_schs.as_slice().join(" "),
                ),
            ));
        }
        let mut des_opts = self.options.clone();
        des_opts.sort_unstable();

        let mut cur_opts: Vec<String> = current
            .config
            .as_ref()
            .and_then(|c| c.options.as_ref())
            .cloned()
            .unwrap_or_default();

        cur_opts.sort_unstable();

        if des_opts != cur_opts {
            return Err(NmstateError::new(
                ErrorKind::VerificationError,
                format!(
                    "Failed to apply DNS config: desire options '{}', \
                    got '{}'",
                    des_opts.as_slice().join(" "),
                    cur_opts.as_slice().join(" "),
                ),
            ));
        }

        Ok(())
    }
}
