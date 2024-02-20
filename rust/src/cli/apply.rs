// SPDX-License-Identifier: Apache-2.0

use std::fs::File;
use std::io::{stdin, stdout, Read, Write};
use std::process::{Command, Stdio};
use std::str::FromStr;

use nmstate::{NetworkPolicy, NetworkState};

use crate::{config::Config, error::CliError};

const DEFAULT_TIMEOUT: u32 = 60;

pub(crate) fn apply_from_stdin(
    matches: &clap::ArgMatches,
) -> Result<String, CliError> {
    set_ctrl_c_action();
    apply(&mut stdin(), matches)
}

pub(crate) fn apply_from_files(
    file_paths: &[&str],
    matches: &clap::ArgMatches,
) -> Result<String, CliError> {
    set_ctrl_c_action();

    let mut ret = String::new();
    for file_path in file_paths {
        ret += &apply(&mut std::fs::File::open(file_path)?, matches)?;
    }
    Ok(ret)
}

pub(crate) fn apply<R>(
    reader: &mut R,
    matches: &clap::ArgMatches,
) -> Result<String, CliError>
where
    R: Read,
{
    let kernel_only = matches.try_contains_id("KERNEL").unwrap_or_default();
    let no_verify = matches.try_contains_id("NO_VERIFY").unwrap_or_default();
    let no_commit = matches.try_contains_id("NO_COMMIT").unwrap_or_default();
    let timeout = if matches.try_contains_id("TIMEOUT").unwrap_or_default() {
        match matches.try_get_one::<String>("TIMEOUT") {
            Ok(Some(t)) => match u32::from_str(t) {
                Ok(i) => i,
                Err(e) => {
                    return Err(CliError {
                        code: crate::error::EX_DATAERR,
                        error_msg: e.to_string(),
                    });
                }
            },
            Ok(None) => DEFAULT_TIMEOUT,
            Err(e) => {
                return Err(CliError {
                    code: crate::error::EX_DATAERR,
                    error_msg: e.to_string(),
                });
            }
        }
    } else {
        DEFAULT_TIMEOUT
    };
    let backend_opts: Vec<String> = match matches
        .try_get_one::<String>("BACKEND_OPTIONS")
    {
        Ok(Some(t)) => t.split(',').map(|s| s.to_string()).collect(),
        Ok(None) => {
            let config_path =
                if let Ok(Some(p)) = matches.try_get_one::<String>("CONFIG") {
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

    let mut content = String::new();
    // Replace non-breaking space '\u{A0}'  to normal space
    reader.read_to_string(&mut content)?;
    let content = content.replace('\u{A0}', " ");

    let mut net_state: NetworkState = match serde_yaml::from_str(&content) {
        Ok(s) => s,
        Err(state_error) => {
            // Try NetworkPolicy
            let net_policy: NetworkPolicy = match serde_yaml::from_str(&content)
            {
                Ok(p) => p,
                Err(policy_error) => {
                    let e = if content.contains("desiredState")
                        || content.contains("desired")
                    {
                        policy_error
                    } else {
                        state_error
                    };
                    return Err(CliError::from(format!(
                        "Provide file is not valid NetworkState or \
                        NetworkPolicy: {e}"
                    )));
                }
            };
            NetworkState::try_from(net_policy)?
        }
    };

    net_state.set_kernel_only(kernel_only);
    net_state.set_verify_change(!no_verify);
    net_state.set_commit(!no_commit);
    net_state.set_timeout(timeout);
    net_state.set_memory_only(
        matches.try_contains_id("MEMORY_ONLY").unwrap_or_default(),
    );
    if !backend_opts.is_empty() {
        net_state.set_backend_options(backend_opts);
    }

    net_state.apply()?;
    if !matches.try_contains_id("SHOW_SECRETS").unwrap_or_default() {
        net_state.hide_secrets();
    }
    let sorted_net_state = crate::query::sort_netstate(net_state)?;
    Ok(serde_yaml::to_string(&sorted_net_state)?)
}

pub(crate) fn commit(checkpoint: &str) -> Result<String, CliError> {
    match NetworkState::checkpoint_commit(checkpoint) {
        Ok(()) => Ok(checkpoint.to_string()),
        Err(e) => Err(CliError::from(e)),
    }
}

pub(crate) fn rollback(checkpoint: &str) -> Result<String, CliError> {
    match NetworkState::checkpoint_rollback(checkpoint) {
        Ok(()) => Ok(checkpoint.to_string()),
        Err(e) => Err(CliError::from(e)),
    }
}

pub(crate) fn state_edit(
    matches: &clap::ArgMatches,
) -> Result<String, CliError> {
    let mut cur_state = NetworkState::new();
    if matches.is_present("KERNEL") {
        cur_state.set_kernel_only(true);
    }
    cur_state.set_running_config_only(true);
    cur_state.retrieve()?;
    let net_state = if let Some(ifname) = matches.value_of("IFNAME") {
        let mut net_state = NetworkState::new();
        for iface in cur_state
            .interfaces
            .to_vec()
            .iter()
            .filter(|i| i.name() == ifname)
        {
            net_state.append_interface_data((*iface).clone());
        }
        if net_state.interfaces.to_vec().is_empty() {
            return Err(CliError {
                code: crate::error::EX_DATAERR,
                error_msg: format!("Interface {ifname} not found"),
            });
        }
        net_state
    } else {
        cur_state
    };
    let tmp_file_path = gen_tmp_file_path();
    write_state_to_file(&tmp_file_path, &net_state)?;
    let mut desire_state = run_editor(&tmp_file_path)?;
    del_file(&tmp_file_path);
    desire_state.set_kernel_only(matches.is_present("KERNEL"));
    desire_state.set_verify_change(!matches.is_present("NO_VERIFY"));
    desire_state.set_commit(!matches.is_present("NO_COMMIT"));
    desire_state.set_memory_only(matches.is_present("MEMORY_ONLY"));
    desire_state.apply()?;
    Ok(serde_yaml::to_string(&desire_state)?)
}

fn gen_tmp_file_path() -> String {
    format!(
        "{}/nmstate-{}.yml",
        std::env::temp_dir().display(),
        uuid::Uuid::new_v4()
    )
}

fn del_file(file_path: &str) {
    if let Err(e) = std::fs::remove_file(file_path) {
        eprintln!("Failed to delete file {file_path}: {e}");
    }
}

fn write_state_to_file(
    file_path: &str,
    net_state: &NetworkState,
) -> Result<(), CliError> {
    let mut fd = File::create(file_path)?;
    fd.write_all(serde_yaml::to_string(net_state)?.as_bytes())?;
    Ok(())
}

fn run_editor(tmp_file_path: &str) -> Result<NetworkState, CliError> {
    let editor = match std::env::var("EDITOR") {
        Ok(e) => e,
        Err(_) => "vi".to_string(),
    };
    loop {
        let mut child = Command::new(&editor)
            .arg(tmp_file_path)
            .stdin(Stdio::inherit())
            .stderr(Stdio::inherit())
            .stdout(Stdio::inherit())
            .spawn()?;
        if !child
            .wait()
            .map_err(|e| CliError {
                code: crate::error::EX_DATAERR,
                error_msg: format!("Editor '{editor}' failed with {e}"),
            })?
            .success()
        {
            return Err(CliError {
                code: crate::error::EX_DATAERR,
                error_msg: format!("Editor '{editor}' failed"),
            });
        }
        let fd = std::fs::File::open(tmp_file_path)?;
        match serde_yaml::from_reader(fd) {
            Ok(n) => return Ok(n),
            Err(e) => {
                if !ask_for_retry() {
                    return Err(CliError {
                        code: crate::error::EX_DATAERR,
                        error_msg: format!("{e}"),
                    });
                } else {
                    eprintln!("{e}");
                    continue;
                }
            }
        }
    }
}

fn ask_for_retry() -> bool {
    loop {
        println!(
            "Try again? [y,n]:\n\
            y - yes, start editor again\n\
            n - no, throw away my changes\n\
            > "
        );
        stdout().lock().flush().ok();
        let mut retry = String::new();
        stdin().read_line(&mut retry).expect("Failed to read line");
        retry.make_ascii_lowercase();
        match retry.trim() {
            "y" | "yes" => return true,
            "n" | "no" => return false,
            _ => println!("Invalid reply, please try y or n"),
        }
    }
}

fn set_ctrl_c_action() {
    ctrlc::set_handler(|| {
        if let Err(e) = rollback("") {
            println!("Failed to rollback: {e}");
        }
        std::process::exit(1);
    })
    .expect("Error setting Ctrl-C handler");
}
