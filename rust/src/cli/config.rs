// SPDX-License-Identifier: Apache-2.0

use std::io::Read;

use serde::Deserialize;

use crate::error::CliError;

#[derive(Debug, Default, Deserialize)]
pub(crate) struct Config {
    #[serde(default)]
    pub(crate) service: ServiceConfig,
    #[serde(default)]
    pub(crate) apply: ApplyConfig,
}

#[derive(Debug, Default, Deserialize)]
pub(crate) struct ServiceConfig {
    #[serde(default)]
    pub(crate) keep_state_file_after_apply: bool,
}

#[derive(Debug, Default, Deserialize)]
pub(crate) struct ApplyConfig {
    #[serde(default)]
    pub(crate) backend_options: Vec<String>,
}

impl Config {
    pub(crate) const DEFAULT_CONFIG_FILE_NAME: &'static str = "nmstate.conf";
    pub(crate) const DEFAULT_CONFIG_PATH: &'static str =
        "/etc/nmstate/nmstate.conf";

    pub(crate) fn load(path: &str) -> Result<Self, CliError> {
        let path = std::path::Path::new(path);
        if !path.exists() {
            return Ok(Config::default());
        }
        let mut fd = std::fs::File::open(path)?;
        let mut content = String::new();
        fd.read_to_string(&mut content)?;
        match toml::from_str::<Config>(&content) {
            Ok(c) => {
                log::info!("Configuration loaded:\n{content}");
                Ok(c)
            }
            Err(e) => Err(CliError::from(format!(
                "Failed to read configuration from {}: {e}",
                path.display()
            ))),
        }
    }
}
