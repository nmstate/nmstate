// SPDX-License-Identifier: Apache-2.0

#[cfg(feature = "query_apply")]
mod apply;
#[cfg(feature = "query_apply")]
mod autoconf;
mod error;
mod format;
#[cfg(feature = "gen_conf")]
mod gen_conf;
#[cfg(feature = "query_apply")]
pub(crate) mod persist_nic;
#[cfg(feature = "query_apply")]
mod policy;
#[cfg(feature = "query_apply")]
mod query;
mod result;
#[cfg(feature = "query_apply")]
mod service;

use env_logger::Builder;
use log::LevelFilter;

#[cfg(feature = "query_apply")]
use crate::apply::{
    apply_from_files, apply_from_stdin, commit, rollback, state_edit,
};
#[cfg(feature = "query_apply")]
use crate::autoconf::autoconf;
#[cfg(feature = "gen_conf")]
use crate::gen_conf::gen_conf;
#[cfg(feature = "query_apply")]
use crate::policy::policy;
#[cfg(feature = "query_apply")]
use crate::query::show;
use crate::result::print_result_and_exit;
#[cfg(feature = "query_apply")]
use crate::service::ncl_service;

pub(crate) const DEFAULT_SERVICE_FOLDER: &str = "/etc/nmstate";
pub(crate) const CONFIG_FOLDER_KEY: &str = "CONFIG_FOLDER";

const APP_NAME: &str = "nmstatectl";

const SUB_CMD_GEN_CONF: &str = "gc";
const SUB_CMD_SHOW: &str = "show";
const SUB_CMD_APPLY: &str = "apply";
const SUB_CMD_COMMIT: &str = "commit";
const SUB_CMD_ROLLBACK: &str = "rollback";
const SUB_CMD_EDIT: &str = "edit";
const SUB_CMD_VERSION: &str = "version";
const SUB_CMD_AUTOCONF: &str = "autoconf";
const SUB_CMD_SERVICE: &str = "service";
const SUB_CMD_PERSIST_NIC_NAMES: &str = "persist-nic-names";
const SUB_CMD_POLICY: &str = "policy";
const SUB_CMD_FORMAT: &str = "format";

fn main() {
    let argv: Vec<String> = std::env::args().collect();
    if argv[0].ends_with("-autoconf") {
        print_result_and_exit(autoconf(argv.as_slice()));
    }
    if argv.get(1) == Some(&"autoconf".to_string()) {
        print_result_and_exit(autoconf(&argv[1..]));
    }

    let mut app = clap::Command::new(APP_NAME)
        .version(clap::crate_version!())
        .author("Gris Ge <fge@redhat.com>")
        .about("Command line of nmstate")
        .subcommand_required(true)
        .arg(
            clap::Arg::new("verbose")
                .short('v')
                .multiple_occurrences(true)
                .help("Set verbose level")
                .global(true),
        )
        .arg(
            clap::Arg::new("quiet")
                .short('q')
                .help("Disable logging")
                .global(true),
        )
        .subcommand(
            clap::Command::new(SUB_CMD_AUTOCONF)
                .about(
                    "Automatically configure network base on LLDP \
                    information(experimental)")
        )
        .subcommand(
            clap::Command::new(SUB_CMD_SHOW)
                .about("Show network state")
                .arg(
                    clap::Arg::new("IFNAME")
                        .index(1)
                        .help("Show specific interface only"),
                )
                .arg(
                    clap::Arg::new("KERNEL")
                        .short('k')
                        .long("kernel")
                        .takes_value(false)
                        .help("Show kernel network state only")
                )
                .arg(
                    clap::Arg::new("JSON")
                        .long("json")
                        .takes_value(false)
                        .help("Show state in json format"),
                )
                .arg(
                    clap::Arg::new("RUNNING_CONFIG_ONLY")
                        .short('r')
                        .long("running-config")
                        .takes_value(false)
                        .help("Show running configuration only"),
                )
                .arg(
                    clap::Arg::new("SHOW_SECRETS")
                        .short('s')
                        .long("show-secrets")
                        .takes_value(false)
                        .help("Show secrets(hide by default)"),
                )
        )
        .subcommand(
            clap::Command::new(SUB_CMD_APPLY)
                .about("Apply network state or network policy")
                .alias("set")
                .arg(
                    clap::Arg::new("STATE_FILE")
                        .required(false)
                        .multiple_occurrences(true)
                        .index(1)
                        .help("Network state file"),
                )
                .arg(
                    clap::Arg::new("NO_VERIFY")
                        .long("no-verify")
                        .takes_value(false)
                        .help(
                            "Do not verify that the state was completely set \
                            and disable rollback to previous state.",
                        ),
                )
                .arg(
                    clap::Arg::new("KERNEL")
                        .short('k')
                        .long("kernel")
                        .takes_value(false)
                        .help("Apply network state to kernel only"),
                )
                .arg(
                    clap::Arg::new("NO_COMMIT")
                      .long("no-commit")
                      .takes_value(false)
                      .help(
                        "Do not commit new state after verification"
                      ),
                )
                .arg(
                    clap::Arg::new("TIMEOUT")
                      .long("timeout")
                      .takes_value(true)
                      .help(
                        "Timeout in seconds before reverting uncommited changes."
                      ),
                )
                .arg(
                    clap::Arg::new("SHOW_SECRETS")
                        .short('s')
                        .long("show-secrets")
                        .takes_value(false)
                        .help("Show secrets(hide by default)"),
                )
                .arg(
                    clap::Arg::new("MEMORY_ONLY")
                        .long("memory-only")
                        .takes_value(false)
                        .help("Do not make the state persistent"),
                )
        )
        .subcommand(
            clap::Command::new(SUB_CMD_GEN_CONF)
                .about("Generate network configuration for specified state")
                .arg(
                    clap::Arg::new("STATE_FILE")
                        .required(true)
                        .index(1)
                        .help("Network state file"),
                ),
        )
        .subcommand(
            clap::Command::new(SUB_CMD_COMMIT)
                .about("Commit a change")
                .arg(
                    clap::Arg::new("CHECKPOINT")
                        .required(false)
                        .index(1)
                        .help("checkpoint to commit"),
                ),
        )
        .subcommand(
            clap::Command::new(SUB_CMD_ROLLBACK)
                .about("Commit a change")
                .arg(
                    clap::Arg::new("CHECKPOINT")
                        .required(false)
                        .index(1)
                        .help("checkpoint to rollback"),
                ),
        )
        .subcommand(
            clap::Command::new(SUB_CMD_EDIT)
                .about("Edit network state in EDITOR")
                .arg(
                    clap::Arg::new("IFNAME")
                        .required(false)
                        .index(1)
                        .help("Interface to rollback"),
                )
                .arg(
                    clap::Arg::new("NO_VERIFY")
                        .long("no-verify")
                        .takes_value(false)
                        .help(
                            "Do not verify that the state was completely set \
                            and disable rollback to previous state.",
                        ),
                )
                .arg(
                    clap::Arg::new("KERNEL")
                        .short('k')
                        .long("kernel")
                        .takes_value(false)
                        .help("Apply network state to kernel only"),
                )
                .arg(
                    clap::Arg::new("NO_COMMIT")
                      .long("no-commit")
                      .takes_value(false)
                      .help(
                        "Do not commit new state after verification"
                      ),
                )
                .arg(
                    clap::Arg::new("MEMORY_ONLY")
                        .long("memory-only")
                        .takes_value(false)
                        .help("Do not make the state persistent"),
                )
        )
        .subcommand(
            clap::Command::new(SUB_CMD_SERVICE)
                .about("Service mode: apply files from service folder")
                .arg(
                    clap::Arg::new(CONFIG_FOLDER_KEY)
                        .long("config")
                        .short('c')
                        .required(false)
                        .takes_value(true)
                        .default_value(DEFAULT_SERVICE_FOLDER)
                        .help("Folder hold network state files"),
                ),
        )
        .subcommand(
            clap::Command::new(SUB_CMD_POLICY)
                .alias("p")
                .about("Generate network state from policy")
                .arg(
                    clap::Arg::new("POLICY_FILE")
                        .required(true)
                        .index(1)
                        .help("Policy file"),
                )
                .arg(
                    clap::Arg::new("CURRENT_STATE")
                        .short('c')
                        .long("current")
                        .takes_value(true)
                        .help("Read current network state from file"),
                )
                .arg(
                    clap::Arg::new("CAPTURED_STATES")
                        .short('a')
                        .long("captured")
                        .takes_value(true)
                        .help("Bypass the capture action by \
                              reading captured network state from \
                              specified file"),
                )
                .arg(
                    clap::Arg::new("OUTPUT_CAPTURED")
                        .short('o')
                        .long("output-captured")
                        .takes_value(true)
                        .help("Store the captured network states to \
                              specified file"),
                )
                .arg(
                    clap::Arg::new("JSON")
                        .long("json")
                        .takes_value(false)
                        .help("Show state in json format"),
                )
        )
        .subcommand(
            clap::Command::new(SUB_CMD_FORMAT)
                .about("Format specified state and print out")
                .alias("f")
                .alias("fmt")
                .arg(
                    clap::Arg::new("STATE_FILE")
                        .index(1)
                        .default_value("-")
                        .help("Network state file"),
                ),
        )
        .subcommand(
            clap::Command::new(SUB_CMD_VERSION)
            .about("Show version")
       );
    if cfg!(feature = "query_apply") {
        app = app.subcommand(
            clap::Command::new(SUB_CMD_PERSIST_NIC_NAMES)
                .about(
                    "Generate .link files which persist active network \
                    interfaces to their current names",
                )
                .arg(
                    clap::Arg::new("DRY_RUN")
                        .long("dry-run")
                        .takes_value(false)
                        .help("Only output changes that would be made"),
                )
                .arg(
                    clap::Arg::new("CLEAN_UP")
                        .long("cleanup")
                        .takes_value(false)
                        .help(
                            "Remove previously created .link files \
                            which has no effect",
                        ),
                )
                .arg(
                    clap::Arg::new("KARGSFILE")
                        .long("kargs-out")
                        .takes_value(true)
                        .help(
                            "When pinning, write kargs to append; \
                            when cleaning up, write kargs to delete \
                            (space-separated)",
                        ),
                )
                .arg(
                    clap::Arg::new("ROOT")
                        .long("root")
                        .short('r')
                        .required(false)
                        .takes_value(true)
                        .default_value("/")
                        .help("Target root filesystem for writing state"),
                )
                // We don't want to expose this outside of OCP yet
                .hide(true),
        );
    };
    let matches = app.get_matches();
    let (log_module_filters, log_level) =
        match matches.occurrences_of("verbose") {
            0 => (vec!["nmstate", "nm_dbus"], LevelFilter::Info),
            1 => (vec!["nmstate", "nm_dbus"], LevelFilter::Debug),
            _ => (vec![""], LevelFilter::Debug),
        };

    if !matches.is_present("quiet") {
        let mut log_builder = Builder::new();
        for log_module_filter in log_module_filters {
            if !log_module_filter.is_empty() {
                log_builder.filter(Some(log_module_filter), log_level);
            } else {
                log_builder.filter(None, log_level);
            }
        }
        log_builder.init();
    }

    if let Some(matches) = matches.subcommand_matches(SUB_CMD_GEN_CONF) {
        if let Some(file_path) = matches.value_of("STATE_FILE") {
            print_result_and_exit(gen_conf(file_path));
        }
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_SHOW) {
        print_result_and_exit(show(matches));
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_APPLY) {
        if argv.get(1) == Some(&"set".to_string()) {
            eprintln!("Using 'set' is deprecated, use 'apply' instead.");
        }

        if let Some(file_paths) = matches.values_of("STATE_FILE") {
            let file_paths: Vec<&str> = file_paths.collect();
            if file_paths.first() == Some(&"-") {
                print_result_and_exit(apply_from_stdin(matches));
            } else {
                print_result_and_exit(apply_from_files(&file_paths, matches));
            }
        } else {
            print_result_and_exit(apply_from_stdin(matches));
        }
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_COMMIT) {
        if let Some(checkpoint) = matches.value_of("CHECKPOINT") {
            print_result_and_exit(commit(checkpoint));
        } else {
            print_result_and_exit(commit(""))
        }
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_ROLLBACK) {
        if let Some(checkpoint) = matches.value_of("CHECKPOINT") {
            print_result_and_exit(rollback(checkpoint));
        } else {
            print_result_and_exit(rollback(""))
        }
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_EDIT) {
        print_result_and_exit(state_edit(matches));
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_SERVICE) {
        print_result_and_exit(ncl_service(matches));
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_POLICY) {
        print_result_and_exit(policy(matches));
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_FORMAT) {
        // The default_value() has ensured the unwrap() will never fail
        print_result_and_exit(format::format(
            matches.value_of("STATE_FILE").unwrap(),
        ));
    } else if matches.subcommand_matches(SUB_CMD_VERSION).is_some() {
        print_result_and_exit(Ok(format!(
            "{} {}",
            APP_NAME,
            clap::crate_version!()
        )));
    } else {
        // Conditionally-built commands
        #[cfg(feature = "query_apply")]
        if let Some(matches) =
            matches.subcommand_matches(SUB_CMD_PERSIST_NIC_NAMES)
        {
            let action = if matches
                .try_contains_id("DRY_RUN")
                .unwrap_or_default()
            {
                if matches.try_contains_id("CLEAN_UP").unwrap_or_default() {
                    persist_nic::PersistAction::CleanUpDryRun
                } else {
                    persist_nic::PersistAction::DryRun
                }
            } else if matches.try_contains_id("CLEAN_UP").unwrap_or_default() {
                persist_nic::PersistAction::CleanUp
            } else {
                persist_nic::PersistAction::Save
            };
            print_result_and_exit(crate::persist_nic::run_persist_immediately(
                matches.value_of("ROOT").unwrap(),
                matches.value_of("KARGSFILE"),
                action,
            ));
        }
    }
}

#[cfg(not(feature = "gen_conf"))]
fn gen_conf(_file_path: &str) -> Result<String, crate::error::CliError> {
    Err("The gc sub-command require `gen_conf` feature been \
        enabled during compiling"
        .into())
}

#[cfg(not(feature = "query_apply"))]
fn show(_matches: &clap::ArgMatches) -> Result<String, crate::error::CliError> {
    Err("The show sub-command require `query_apply` feature been \
        enabled during compiling"
        .into())
}

#[cfg(not(feature = "query_apply"))]
fn apply_from_stdin(
    _matches: &clap::ArgMatches,
) -> Result<String, crate::error::CliError> {
    Err("The apply sub-command require `query_apply` feature been \
        enabled during compiling"
        .into())
}

#[cfg(not(feature = "query_apply"))]
fn apply_from_files(
    _file_paths: &[&str],
    _matches: &clap::ArgMatches,
) -> Result<String, crate::error::CliError> {
    Err("The apply sub-command require `query_apply` feature been \
        enabled during compiling"
        .into())
}

#[cfg(not(feature = "query_apply"))]
fn commit(_checkpoint: &str) -> Result<String, crate::error::CliError> {
    Err("The commit sub-command require `query_apply` feature been \
        enabled during compiling"
        .into())
}

#[cfg(not(feature = "query_apply"))]
fn rollback(_checkpoint: &str) -> Result<String, crate::error::CliError> {
    Err(
        "The rollback sub-command require `query_apply` feature been \
        enabled during compiling"
            .into(),
    )
}

#[cfg(not(feature = "query_apply"))]
fn state_edit(
    _matches: &clap::ArgMatches,
) -> Result<String, crate::error::CliError> {
    Err("The edit sub-command require `query_apply` feature been \
        enabled during compiling"
        .into())
}

#[cfg(not(feature = "query_apply"))]
fn autoconf(_argv: &[String]) -> Result<String, crate::error::CliError> {
    Err(
        "The autoconf sub-command require `query_apply` feature been \
        enabled during compiling"
            .into(),
    )
}

#[cfg(not(feature = "query_apply"))]
fn ncl_service(
    _matches: &clap::ArgMatches,
) -> Result<String, crate::error::CliError> {
    Err(
        "The service sub-command require `query_apply` feature been \
        enabled during compiling"
            .into(),
    )
}

#[cfg(not(feature = "query_apply"))]
fn policy(
    _matches: &clap::ArgMatches,
) -> Result<String, crate::error::CliError> {
    Err("The policy sub-command require `query_apply` feature been \
        enabled during compiling"
        .into())
}
