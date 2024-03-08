// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, HostNameState, MergedHostNameState, NmstateError};

impl HostNameState {
    pub(crate) fn update(&mut self, other: &Self) {
        if other.running.is_some() {
            self.running.clone_from(&other.running);
        }
        if other.config.is_some() {
            self.config.clone_from(&other.config);
        }
    }
}

impl MergedHostNameState {
    pub(crate) fn verify(
        &self,
        current: Option<&HostNameState>,
    ) -> Result<(), NmstateError> {
        let desired = if let Some(d) = &self.desired {
            d
        } else {
            return Ok(());
        };
        let current = if let Some(c) = current {
            c
        } else {
            return Err(NmstateError::new(
                ErrorKind::Bug,
                "MergedHostNameState::verify(): Got current \
                HostNameState set to None"
                    .to_string(),
            ));
        };

        if let Some(running) = desired.running.as_ref() {
            if Some(running) != current.running.as_ref() {
                let e = NmstateError::new(
                    ErrorKind::VerificationError,
                    format!(
                        "Verification fail, desire hostname.running: \
                        {}, current: {:?}",
                        running,
                        current.running.as_ref()
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }
        if let Some(config) = desired.config.as_ref() {
            if Some(config) != current.config.as_ref() {
                let e = NmstateError::new(
                    ErrorKind::VerificationError,
                    format!(
                        "Verification fail, desire hostname.config: \
                        {}, current: {:?}",
                        config,
                        current.config.as_ref()
                    ),
                );
                log::error!("{}", e);
                return Err(e);
            }
        }

        Ok(())
    }
}
