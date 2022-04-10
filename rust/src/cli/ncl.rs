mod error;

use std::fs::File;
use std::io::{self, stdin, stdout, Read, Write};
use std::process::{Command, Stdio};

use env_logger::Builder;
use log::LevelFilter;
use nmstate::{DnsState, NetworkState, OvsDbGlobalConfig, RouteRules, Routes};
use serde::Serialize;
use serde_yaml::{self, Value};

use crate::error::CliError;

const APP_NAME: &str = "nmstatectl";

const SUB_CMD_GEN_CONF: &str = "gc";
const SUB_CMD_SHOW: &str = "show";
const SUB_CMD_APPLY: &str = "apply";
const SUB_CMD_COMMIT: &str = "commit";
const SUB_CMD_ROLLBACK: &str = "rollback";
const SUB_CMD_EDIT: &str = "edit";
const SUB_CMD_VERSION: &str = "version";

const EX_DATAERR: i32 = 65;
const EXIT_FAILURE: i32 = 1;

fn main() {
    let matches = clap::App::new(APP_NAME)
        .version(clap::crate_version!())
        .author("Gris Ge <fge@redhat.com>")
        .about("Command line of nmstate")
        .setting(clap::AppSettings::SubcommandRequired)
        .arg(
            clap::Arg::with_name("verbose")
                .short("v")
                .multiple(true)
                .help("Set verbose level")
                .global(true),
        )
        .subcommand(
            clap::SubCommand::with_name(SUB_CMD_SHOW)
                .about("Show network state")
                .arg(
                    clap::Arg::with_name("IFNAME")
                        .index(1)
                        .help("Show specific interface only"),
                )
                .arg(
                    clap::Arg::with_name("KERNEL")
                        .short("k")
                        .long("kernel")
                        .takes_value(false)
                        .help("Show kernel network state only")
                )
                .arg(
                    clap::Arg::with_name("JSON")
                        .long("json")
                        .takes_value(false)
                        .help("Show state in json format"),
                )
                .arg(
                    clap::Arg::with_name("RUNNING_CONFIG_ONLY")
                        .short("r")
                        .long("running-config")
                        .takes_value(false)
                        .help("Show running configuration only"),
                )
                .arg(
                    clap::Arg::with_name("SHOW_SECRETS")
                        .short("s")
                        .long("show-secrets")
                        .takes_value(false)
                        .help("Show secrets(hide by default)"),
                )
        )
        .subcommand(
            clap::SubCommand::with_name(SUB_CMD_APPLY)
                .about("Apply network state")
                .alias("set")
                .arg(
                    clap::Arg::with_name("STATE_FILE")
                        .required(false)
                        .index(1)
                        .help("Network state file"),
                )
                .arg(
                    clap::Arg::with_name("NO_VERIFY")
                        .long("no-verify")
                        .takes_value(false)
                        .help(
                            "Do not verify that the state was completely set \
                            and disable rollback to previous state.",
                        ),
                )
                .arg(
                    clap::Arg::with_name("KERNEL")
                        .short("k")
                        .long("kernel")
                        .takes_value(false)
                        .help("Apply network state to kernel only"),
                )
                .arg(
                    clap::Arg::with_name("NO_COMMIT")
                      .long("no-commit")
                      .takes_value(false)
                      .help(
                        "Do not commit new state after verification"
                      ),
                )
                .arg(
                    clap::Arg::with_name("TIMEOUT")
                      .long("timeout")
                      .takes_value(true)
                      .default_value("60")
                      .help(
                        "Timeout in seconds before reverting uncommited changes."
                      ),
                )
                .arg(
                    clap::Arg::with_name("SHOW_SECRETS")
                        .short("s")
                        .long("show-secrets")
                        .takes_value(false)
                        .help("Show secrets(hide by default)"),
                )
                .arg(
                    clap::Arg::with_name("MEMORY_ONLY")
                        .long("memory-only")
                        .takes_value(false)
                        .help("Do not make the state persistent"),
                )
        )
        .subcommand(
            clap::SubCommand::with_name(SUB_CMD_GEN_CONF)
                .about("Generate network configuration for specified state")
                .arg(
                    clap::Arg::with_name("STATE_FILE")
                        .required(true)
                        .index(1)
                        .help("Network state file"),
                ),
        )
        .subcommand(
            clap::SubCommand::with_name(SUB_CMD_COMMIT)
                .about("Commit a change")
                .arg(
                    clap::Arg::with_name("CHECKPOINT")
                        .required(false)
                        .index(1)
                        .help("checkpoint to commit"),
                ),
        )
        .subcommand(
            clap::SubCommand::with_name(SUB_CMD_ROLLBACK)
                .about("Commit a change")
                .arg(
                    clap::Arg::with_name("CHECKPOINT")
                        .required(false)
                        .index(1)
                        .help("checkpoint to rollback"),
                ),
        )
        .subcommand(
            clap::SubCommand::with_name(SUB_CMD_EDIT)
                .about("Edit network state in EDITOR")
                .arg(
                    clap::Arg::with_name("IFNAME")
                        .required(false)
                        .index(1)
                        .help("Interface to rollback"),
                )
                .arg(
                    clap::Arg::with_name("NO_VERIFY")
                        .long("no-verify")
                        .takes_value(false)
                        .help(
                            "Do not verify that the state was completely set \
                            and disable rollback to previous state.",
                        ),
                )
                .arg(
                    clap::Arg::with_name("KERNEL")
                        .short("k")
                        .long("kernel")
                        .takes_value(false)
                        .help("Apply network state to kernel only"),
                )
                .arg(
                    clap::Arg::with_name("NO_COMMIT")
                      .long("no-commit")
                      .takes_value(false)
                      .help(
                        "Do not commit new state after verification"
                      ),
                )
                .arg(
                    clap::Arg::with_name("MEMORY_ONLY")
                        .long("memory-only")
                        .takes_value(false)
                        .help("Do not make the state persistent"),
                )
        )
        .subcommand(
            clap::SubCommand::with_name(SUB_CMD_VERSION)
            .about("Show version")
       ).get_matches();
    let (log_module_filters, log_level) =
        match matches.occurrences_of("verbose") {
            0 => (vec!["nmstate", "nm_dbus"], LevelFilter::Warn),
            1 => (vec!["nmstate", "nm_dbus"], LevelFilter::Info),
            2 => (vec!["nmstate", "nm_dbus"], LevelFilter::Debug),
            _ => (vec![""], LevelFilter::Debug),
        };

    let mut log_builder = Builder::new();
    for log_module_filter in log_module_filters {
        if !log_module_filter.is_empty() {
            log_builder.filter(Some(log_module_filter), log_level);
        } else {
            log_builder.filter(None, log_level);
        }
    }
    log_builder.init();

    if let Some(matches) = matches.subcommand_matches(SUB_CMD_GEN_CONF) {
        if let Some(file_path) = matches.value_of("STATE_FILE") {
            print_result_and_exit(gen_conf(file_path), EX_DATAERR);
        }
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_SHOW) {
        print_result_and_exit(show(matches), EXIT_FAILURE);
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_APPLY) {
        if let Some(file_path) = matches.value_of("STATE_FILE") {
            print_result_and_exit(
                apply_from_file(file_path, matches),
                EX_DATAERR,
            );
        } else {
            print_result_and_exit(apply_from_stdin(matches), EX_DATAERR);
        }
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_COMMIT) {
        if let Some(checkpoint) = matches.value_of("CHECKPOINT") {
            print_result_and_exit(commit(checkpoint), EXIT_FAILURE);
        } else {
            print_result_and_exit(commit(""), EXIT_FAILURE)
        }
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_ROLLBACK) {
        if let Some(checkpoint) = matches.value_of("CHECKPOINT") {
            print_result_and_exit(rollback(checkpoint), EXIT_FAILURE);
        } else {
            print_result_and_exit(rollback(""), EXIT_FAILURE)
        }
    } else if let Some(matches) = matches.subcommand_matches(SUB_CMD_EDIT) {
        print_result_and_exit(state_edit(matches), EX_DATAERR);
    } else if matches.subcommand_matches(SUB_CMD_VERSION).is_some() {
        print_string_and_exit(format!(
            "{} {}",
            APP_NAME,
            clap::crate_version!()
        ));
    }
}

// Use T instead of String where T has Serialize
fn print_result_and_exit(result: Result<String, CliError>, errno: i32) {
    match result {
        Ok(s) => print_string_and_exit(s),
        Err(e) => print_error_and_exit(e, errno),
    }
}

fn print_error_and_exit(e: CliError, errno: i32) {
    eprintln!("{}", e);
    std::process::exit(errno);
}

fn print_string_and_exit(s: String) {
    println!("{}", s);
    std::process::exit(0);
}

fn gen_conf(file_path: &str) -> Result<String, CliError> {
    let fd = std::fs::File::open(file_path)?;
    let net_state: NetworkState = serde_yaml::from_reader(fd)?;
    let confs = net_state.gen_conf()?;
    Ok(serde_yaml::to_string(&confs)?)
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct SortedNetworkState {
    dns: DnsState,
    rules: RouteRules,
    routes: Routes,
    interfaces: Vec<Value>,
    #[serde(rename = "ovs-db")]
    ovsdb: OvsDbGlobalConfig,
}

const IFACE_TOP_PRIORTIES: [&str; 2] = ["name", "type"];

fn sort_netstate(
    net_state: NetworkState,
) -> Result<SortedNetworkState, CliError> {
    let mut ifaces = net_state.interfaces.to_vec();
    ifaces.sort_by(|a, b| a.name().cmp(b.name()));

    if let Value::Sequence(ifaces) = serde_yaml::to_value(&ifaces)? {
        let mut new_ifaces = Vec::new();
        for iface_v in ifaces {
            if let Value::Mapping(iface) = iface_v {
                let mut new_iface = serde_yaml::Mapping::new();
                for top_property in &IFACE_TOP_PRIORTIES {
                    if let Some(v) =
                        iface.get(&Value::String(top_property.to_string()))
                    {
                        new_iface.insert(
                            Value::String(top_property.to_string()),
                            v.clone(),
                        );
                    }
                }
                for (k, v) in iface.iter() {
                    if let Value::String(ref name) = k {
                        if IFACE_TOP_PRIORTIES.contains(&name.as_str()) {
                            continue;
                        }
                    }
                    new_iface.insert(k.clone(), v.clone());
                }

                new_ifaces.push(Value::Mapping(new_iface));
            }
        }
        return Ok(SortedNetworkState {
            interfaces: new_ifaces,
            routes: net_state.routes,
            rules: net_state.rules,
            dns: net_state.dns,
            ovsdb: net_state.ovsdb,
        });
    }

    Ok(SortedNetworkState {
        interfaces: Vec::new(),
        routes: net_state.routes,
        rules: net_state.rules,
        dns: net_state.dns,
        ovsdb: net_state.ovsdb,
    })
}

// Ordering the outputs
fn show(matches: &clap::ArgMatches) -> Result<String, CliError> {
    let mut net_state = NetworkState::new();
    if matches.is_present("KERNEL") {
        net_state.set_kernel_only(true);
    }
    if matches.is_present("RUNNING_CONFIG_ONLY") {
        net_state.set_running_config_only(true);
    }
    net_state.set_include_secrets(matches.is_present("SHOW_SECRETS"));
    net_state.retrieve()?;
    Ok(if let Some(ifname) = matches.value_of("IFNAME") {
        let mut new_net_state = NetworkState::new();
        new_net_state.set_kernel_only(matches.is_present("KERNEL"));
        for iface in net_state.interfaces.to_vec() {
            if iface.name() == ifname {
                new_net_state.append_interface_data(iface.clone())
            }
        }
        if matches.is_present("JSON") {
            serde_json::to_string_pretty(&new_net_state)?
        } else {
            serde_yaml::to_string(&new_net_state)?
        }
    } else if matches.is_present("JSON") {
        serde_json::to_string_pretty(&sort_netstate(net_state)?)?
    } else {
        serde_yaml::to_string(&sort_netstate(net_state)?)?
    })
}

fn apply_from_stdin(matches: &clap::ArgMatches) -> Result<String, CliError> {
    apply(io::stdin(), matches)
}

fn apply_from_file(
    file_path: &str,
    matches: &clap::ArgMatches,
) -> Result<String, CliError> {
    apply(std::fs::File::open(file_path)?, matches)
}

fn apply<R>(reader: R, matches: &clap::ArgMatches) -> Result<String, CliError>
where
    R: Read,
{
    let kernel_only = matches.is_present("KERNEL");
    let no_verify = matches.is_present("NO_VERIFY");
    let no_commit = matches.is_present("NO_COMMIT");
    let mut timeout: u32 = 0;
    match clap::value_t!(matches.value_of("TIMEOUT"), u32) {
        Ok(t) => timeout = t,
        Err(e) => print_error_and_exit(CliError::from(e), EX_DATAERR),
    }
    let mut net_state: NetworkState = serde_yaml::from_reader(reader)?;
    net_state.set_kernel_only(kernel_only);
    net_state.set_verify_change(!no_verify);
    net_state.set_commit(!no_commit);
    net_state.set_timeout(timeout);
    net_state.set_memory_only(matches.is_present("MEMORY_ONLY"));

    ctrlc::set_handler(|| {
        if let Err(e) = rollback("") {
            println!("Failed to rollback: {}", e);
        }
        std::process::exit(1);
    })
    .expect("Error setting Ctrl-C handler");

    net_state.apply()?;
    if !matches.is_present("SHOW_SECRETS") {
        net_state.hide_secrets();
    }
    let sorted_net_state = sort_netstate(net_state)?;
    Ok(serde_yaml::to_string(&sorted_net_state)?)
}

fn commit(checkpoint: &str) -> Result<String, CliError> {
    match NetworkState::checkpoint_commit(checkpoint) {
        Ok(()) => Ok(checkpoint.to_string()),
        Err(e) => Err(CliError::from(e)),
    }
}

fn rollback(checkpoint: &str) -> Result<String, CliError> {
    match NetworkState::checkpoint_rollback(checkpoint) {
        Ok(()) => Ok(checkpoint.to_string()),
        Err(e) => Err(CliError::from(e)),
    }
}

fn state_edit(matches: &clap::ArgMatches) -> Result<String, CliError> {
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
                msg: format!("Interface {} not found", ifname),
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
        eprintln!("Failed to delete file {}: {}", file_path, e);
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
                msg: format!("Editor '{}' failed with {}", editor, e),
            })?
            .success()
        {
            return Err(CliError {
                msg: format!("Editor '{}' failed", editor),
            });
        }
        let fd = std::fs::File::open(tmp_file_path)?;
        match serde_yaml::from_reader(fd) {
            Ok(n) => return Ok(n),
            Err(e) => {
                if !ask_for_retry() {
                    return Err(CliError {
                        msg: format!("{}", e),
                    });
                } else {
                    eprintln!("{}", e);
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
