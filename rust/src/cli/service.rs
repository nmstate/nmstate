// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;
use std::ffi::OsStr;
use std::fs;
use std::io::Read;
use std::os::unix::fs::MetadataExt;
use std::path::{Path, PathBuf};

use serde::Deserialize;

use crate::{
    apply::apply_state,
    error::CliError,
    state::{state_from_fd, state_from_file},
};

const CONFIG_FILE_EXTENSION: &str = "yml";
const APPLIED_FILE_EXTENSION: &str = "applied";
const CONFIG_FILE_NAME: &str = "nmstate.conf";

#[derive(Debug, Default, Deserialize)]
struct Config {
    #[serde(default)]
    service: ServiceConfig,
}

#[derive(Debug, Default, Deserialize)]
struct ServiceConfig {
    #[serde(default)]
    keep_state_file_after_apply: bool,
    #[serde(default)]
    override_iface: bool,
}

#[derive(Eq, Hash, PartialEq, Clone, PartialOrd, Ord)]
struct FileContent {
    path: PathBuf,
    content: String,
}

impl FileContent {
    fn new(path: PathBuf, content: String) -> Self {
        Self { path, content }
    }
}

pub(crate) fn ncl_service(
    matches: &clap::ArgMatches,
) -> Result<String, CliError> {
    // We ignore the error on loading
    if let Err(e) = ncl_service_run_dir() {
        log::error!(
            "Failed to load desired state file from /run/nmstate folder: {e}"
        );
    }

    let folder = matches
        .value_of(crate::CONFIG_FOLDER_KEY)
        .unwrap_or(crate::DEFAULT_SERVICE_FOLDER);

    let config = load_config(folder)?;

    let state_files = match get_unapplied_state_files(
        folder,
        config.service.keep_state_file_after_apply,
    ) {
        Ok(f) => f,
        Err(e) => {
            log::info!(
                "Failed to read config folder {folder} due to error {e}, \
                 ignoring"
            );
            return Ok(String::new());
        }
    };
    if state_files.is_empty() {
        log::info!(
            "No new nmstate config(end with .{CONFIG_FILE_EXTENSION}) found \
             in config folder {folder}"
        );
        return Ok(String::new());
    }

    // Due to bug of NetworkManager, the `After=NetworkManager.service` in
    // `nmstate.service` cannot guarantee the ready of NM dbus.
    // We sleep for 2 seconds here to avoid meaningless retry.
    std::thread::sleep(std::time::Duration::from_secs(2));

    for state_file in state_files {
        let mut fd = match std::fs::File::open(&state_file.path) {
            Ok(fd) => fd,
            Err(e) => {
                log::error!(
                    "Failed to read config file {}: {e}",
                    state_file.path.display()
                );
                continue;
            }
        };
        let mut state = state_from_fd(&mut fd)?;

        if config.service.override_iface {
            state.set_override_iface(true);
        }

        match apply_state(&state, false) {
            Ok(_) => {
                log::info!(
                    "Applied nmstate config: {}",
                    state_file.path.display()
                );
                if config.service.keep_state_file_after_apply {
                    if let Err(e) =
                        write_content(&state_file.path, &state_file.content)
                    {
                        log::error!(
                            "Failed to generate applied file: {} {}",
                            state_file.path.display(),
                            e
                        );
                    }
                } else if let Err(e) = relocate_file(&state_file.path) {
                    log::error!(
                        "Failed to relocate file {}: {}",
                        state_file.path.display(),
                        e
                    );
                }
            }
            Err(e) => {
                log::error!(
                    "Failed to apply state file {}: {}",
                    state_file.path.display(),
                    e
                );
            }
        }
    }

    Ok("".to_string())
}

// If `keep_state_file_after_apply` is true, we collect all file ending with
// `.yml` that do not have `.applied` file or `.applied` file content changed.
// If `keep_state_file_after_apply` is false, we collect all files ending with
// `.yml`.
fn get_unapplied_state_files(
    folder: &str,
    keep_state_file_after_apply: bool,
) -> Result<Vec<FileContent>, CliError> {
    let folder = Path::new(folder);
    if !folder.exists() {
        log::info!("Folder {} does not exists", folder.display());
        return Ok(Vec::new());
    }
    let mut yml_files = HashSet::<FileContent>::new();
    let mut applied_files = HashSet::<FileContent>::new();
    for entry in folder.read_dir()? {
        let file = entry?.path();
        if file.extension() == Some(OsStr::new(CONFIG_FILE_EXTENSION)) {
            let content = fs::read_to_string(&file)?;
            yml_files.insert(FileContent::new(
                folder.join(file).with_extension(""),
                content,
            ));
        } else if keep_state_file_after_apply
            && file.extension() == Some(OsStr::new(APPLIED_FILE_EXTENSION))
        {
            let content = fs::read_to_string(&file)?;
            applied_files.insert(FileContent::new(
                folder.join(file).with_extension(""),
                content,
            ));
        }
    }
    let mut ret: Vec<_> = yml_files
        .difference(&applied_files)
        .cloned()
        .map(|f| {
            FileContent::new(
                f.path.with_extension(CONFIG_FILE_EXTENSION),
                f.content,
            )
        })
        .collect();
    ret.sort_by_key(|f| f.path.clone());
    Ok(ret)
}

// Dump state to `.applied` file.
pub(crate) fn write_content(
    file_path: &Path,
    content: &str,
) -> Result<(), CliError> {
    let applied_file_path = file_path.with_extension(APPLIED_FILE_EXTENSION);
    fs::write(&applied_file_path, content)?;
    log::info!(
        "Content for config {} stored at {}",
        file_path.display(),
        applied_file_path.display(),
    );
    Ok(())
}

fn load_config(base_cfg_folder: &str) -> Result<Config, CliError> {
    let path = std::path::Path::new(base_cfg_folder).join(CONFIG_FILE_NAME);
    if !path.exists() {
        return Ok(Config::default());
    }
    let mut fd = std::fs::File::open(&path)?;
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

fn relocate_file(file_path: &Path) -> Result<(), CliError> {
    let new_path = file_path.with_extension(APPLIED_FILE_EXTENSION);
    std::fs::rename(file_path, &new_path)?;

    log::info!(
        "Renamed applied config {} to {}",
        file_path.display(),
        new_path.display()
    );
    Ok(())
}

// Read state file from `/run/nmstate` folder, since this folder will
// be purged by OS reboot, nmstate will use `.applied` file to prevent
// second apply.
// For security reason, only file own by root will be loaded.
fn ncl_service_run_dir() -> Result<(), CliError> {
    let folder = Path::new("/run/nmstate");
    if !folder.exists() {
        return Ok(());
    }
    let mut file_paths: Vec<String> = Vec::new();
    for entry in folder.read_dir()? {
        let file = entry?.path();
        if file.extension() == Some(OsStr::new(CONFIG_FILE_EXTENSION)) {
            if let Some(file_path) = folder.join(file).to_str() {
                let meta = fs::metadata(file_path)?;
                if meta.uid() == 0 {
                    file_paths.push(file_path.to_string());
                } else {
                    log::warn!(
                        "Ignoring file {} because it is not own by root",
                        file_path
                    );
                }
            }
        }
    }
    file_paths.sort_unstable();
    for file_path in file_paths {
        let state = match state_from_file(&file_path) {
            Ok(s) => s,
            Err(e) => {
                log::warn!("File {file_path} is not valid nmstate YAML: {e}");
                continue;
            }
        };
        log::info!("Applying desired state from {file_path}");
        match apply_state(&state, false) {
            Ok(_) => {
                log::info!("File {file_path} applied",);
            }

            Err(e) => {
                log::error!("Failed to apply state file {file_path}: {e}",);
            }
        }
    }
    Ok(())
}
