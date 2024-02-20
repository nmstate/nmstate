// SPDX-License-Identifier: Apache-2.0

use crate::{config::Config, error::CliError, state::state_from_file};

pub(crate) fn gen_conf(matches: &clap::ArgMatches) -> Result<String, CliError> {
    if let Some(file_path) = matches.value_of("STATE_FILE") {
        let mut net_state = state_from_file(file_path)?;
        let backend_opts: Vec<String> =
            match matches.try_get_one::<String>("BACKEND_OPTIONS") {
                Ok(Some(t)) => t.split(',').map(|s| s.to_string()).collect(),
                Ok(None) => {
                    let config_path = if let Ok(Some(p)) =
                        matches.try_get_one::<String>("CONFIG")
                    {
                        p.as_str()
                    } else {
                        Config::DEFAULT_CONFIG_PATH
                    };

                    let config = Config::load(config_path)?;
                    config.apply.backend_options
                }
                Err(e) => {
                    return Err(CliError {
                        code: crate::error::EX_DATAERR,
                        error_msg: e.to_string(),
                    });
                }
            };
        if !backend_opts.is_empty() {
            net_state.set_backend_options(backend_opts);
        }

        let confs = net_state.gen_conf()?;
        let escaped_string = serde_yaml::to_string(&confs)?;
        Ok(escaped_string.replace("\\n", "\n\n"))
    } else {
        Err("Please define at least one STATE_FILE".into())
    }
}
