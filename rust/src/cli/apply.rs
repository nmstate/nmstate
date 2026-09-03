// SPDX-License-Identifier: Apache-2.0

use std::{
    fs::File,
    io::{Read, Write, stdin, stdout},
    process::{Command, Stdio},
    str::FromStr,
};

use nmstate::NetworkState;

use crate::{error::CliError, state::state_from_fd};

const DEFAULT_TIMEOUT: u32 = 60;

pub(crate) fn apply_from_stdin(
    matches: &clap::ArgMatches,
) -> Result<String, CliError> {
    apply(&mut stdin(), matches)
}

pub(crate) fn apply_from_files(
    file_paths: &[&str],
    matches: &clap::ArgMatches,
) -> Result<String, CliError> {
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
    let kernel_only = matches.get_flag("KERNEL");
    let no_verify = matches.get_flag("NO_VERIFY");
    let no_commit = matches.get_flag("NO_COMMIT");
    let override_iface = matches.get_flag("OVERRIDE_IFACE");
    let timeout = if let Some(t) = matches.get_one::<String>("TIMEOUT") {
        match u32::from_str(t) {
            Ok(i) => {
                if !no_commit {
                    log::warn!(
                        "--timeout is only effective when used with \
                         --no-commit. The timeout value will be ignored."
                    );
                }
                i
            }
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
    let mut net_state = state_from_fd(reader)?;
    net_state.set_kernel_only(kernel_only);
    net_state.set_verify_change(!no_verify);
    net_state.set_commit(!no_commit);
    net_state.set_timeout(timeout);
    net_state.set_override_iface(override_iface);
    net_state.set_memory_only(matches.get_flag("MEMORY_ONLY"));
    apply_state(&net_state, matches.get_flag("SHOW_SECRETS"))
}

pub(crate) fn apply_state(
    state: &NetworkState,
    show_secrets: bool,
) -> Result<String, CliError> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_io()
        .enable_time()
        .build()
        .map_err(|e| {
            CliError::from(format!("tokio::runtime::Builder failed with {e}"))
        })?;
    let mut diff_state = rt.block_on(apply_state_async(state))?;
    if !show_secrets {
        diff_state.hide_secrets();
    }
    let sorted_net_state = crate::query::sort_netstate(diff_state)?;
    Ok(rmsd_yaml::to_string(&sorted_net_state)?)
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
    if matches.get_flag("KERNEL") {
        cur_state.set_kernel_only(true);
    }
    cur_state.set_running_config_only(true);
    cur_state.retrieve()?;
    let net_state = if let Some(ifname) = matches.get_one::<String>("IFNAME") {
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
        cur_state.clone()
    };
    let tmp_file_path = gen_tmp_file_path();
    write_state_to_file(&tmp_file_path, &net_state)?;
    let mut desire_state = run_editor(&tmp_file_path)?;
    del_file(&tmp_file_path);
    desire_state.set_kernel_only(matches.get_flag("KERNEL"));
    desire_state.set_verify_change(!matches.get_flag("NO_VERIFY"));
    desire_state.set_commit(!matches.get_flag("NO_COMMIT"));
    desire_state.set_memory_only(matches.get_flag("MEMORY_ONLY"));
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_io()
        .enable_time()
        .build()
        .map_err(|e| {
            CliError::from(format!("tokio::runtime::Builder failed with {e}"))
        })?;
    let mut diff_state = rt.block_on(apply_state_async(&desire_state))?;
    // Use try instead of get_flag() because the `edit` sub-command
    // does not have the `SHOW_SECRETS` flag, and try_contains_id() will return
    // an error in this case instead of panic when using `get_flag()`.
    if !matches.try_contains_id("SHOW_SECRETS").unwrap_or_default() {
        diff_state.hide_secrets();
    }
    let sorted_net_state = crate::query::sort_netstate(diff_state)?;
    Ok(rmsd_yaml::to_string(&sorted_net_state)?)
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
    fd.write_all(rmsd_yaml::to_string(net_state)?.as_bytes())?;
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
        match rmsd_yaml::from_reader(fd) {
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
            "Try again? [y,n]:\ny - yes, start editor again\nn - no, throw \
             away my changes\n> "
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

async fn apply_state_async(
    net_state: &NetworkState,
) -> Result<NetworkState, CliError> {
    let mut cur_state = NetworkState::new();
    cur_state.set_kernel_only(net_state.kernel_only());
    cur_state.set_running_config_only(true);
    cur_state.retrieve_async().await?;

    let mut ctrlc_stream = tokio::signal::unix::signal(
        tokio::signal::unix::SignalKind::interrupt(),
    )
    .map_err(|e| format!("tokio failed to hook on signal SIGINT: {e}"))?;
    tokio::select! {
        _ = ctrlc_stream.recv() => {
            NetworkState::checkpoint_rollback_async("").await?;
            Err("Interrupted by SIGINT".into())
        }
        result = net_state.apply_async() => {
            result?;
            match net_state.gen_diff(&cur_state) {
                Ok(s) => Ok(s),
                Err(e) => {
                    log::error!(
                        "BUG: Failed to generate difference: {e}, \
                        returning full desired state");
                    Ok(net_state.clone())
                }
            }
        }
    }
}
