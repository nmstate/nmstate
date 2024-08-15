// SPDX-License-Identifier: Apache-2.0

use super::super::{NmApi, NmError};

// Nmstate does not need to understand level or domains, so we do not parse
// them into enum and Vec<String>.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NmLogConfig {
    pub level: String,
    pub domains: String,
}

impl NmLogConfig {
    pub fn trace_all() -> Self {
        NmLogConfig {
            level: "TRACE".to_string(),
            domains: "ALL".to_string(),
        }
    }
}

impl From<(String, String)> for NmLogConfig {
    fn from(v: (String, String)) -> Self {
        Self {
            level: v.0,
            domains: v.1,
        }
    }
}

impl std::fmt::Display for NmLogConfig {
    fn fmt(
        &self,
        f: &mut std::fmt::Formatter<'_>,
    ) -> Result<(), std::fmt::Error> {
        write!(f, "level: {} domains: {}", self.level, self.domains)
    }
}

impl<'a> NmApi<'a> {
    pub fn get_log_config(&mut self) -> Result<NmLogConfig, NmError> {
        Ok(self.dbus.get_logging()?.into())
    }

    pub fn set_log_config(
        &mut self,
        config: &NmLogConfig,
    ) -> Result<(), NmError> {
        self.dbus
            .set_logging(config.level.as_str(), config.domains.as_str())
    }

    pub fn enable_trace_log(&mut self) -> Result<(), NmError> {
        self.set_log_config(&NmLogConfig::trace_all())
    }
}
