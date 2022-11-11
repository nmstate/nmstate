// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, HostNameState, NmstateError};

impl HostNameState {
    pub(crate) fn update(&mut self, other: &Self) {
        if other.running.is_some() {
            self.running = other.running.clone();
        }
        if other.config.is_some() {
            self.config = other.config.clone();
        }
    }

    pub(crate) fn verify(
        &self,
        current: Option<&Self>,
    ) -> Result<(), NmstateError> {
        let current = if let Some(c) = current {
            c
        } else {
            // Should never happen
            let e = NmstateError::new(
                ErrorKind::Bug,
                "Got None HostNameState as current".to_string(),
            );
            log::error!("{}", e);
            return Err(e);
        };

        if let Some(running) = self.running.as_ref() {
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
        if let Some(config) = self.config.as_ref() {
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
