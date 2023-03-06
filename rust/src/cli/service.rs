// SPDX-License-Identifier: Apache-2.0

use std::ffi::OsStr;
use std::path::{Path, PathBuf};

use crate::{apply::apply, error::CliError};

const CONFIG_FILE_EXTENTION: &str = "yml";
const RELOCATE_FILE_EXTENTION: &str = "applied";

pub(crate) fn ncl_service(
    matches: &clap::ArgMatches,
) -> Result<String, CliError> {
    let folder = matches
        .value_of(crate::CONFIG_FOLDER_KEY)
        .unwrap_or(crate::DEFAULT_SERVICE_FOLDER);

    let config_files = get_config_files(folder)?;
    if config_files.is_empty() {
        log::info!(
            "No nmstate config(end with .{}) found in config folder {}",
            CONFIG_FILE_EXTENTION,
            folder
        );
    }

    for file_path in config_files {
        let mut fd = match std::fs::File::open(&file_path) {
            Ok(fd) => fd,
            Err(e) => {
                log::error!(
                    "Failed to read config file {}: {e}",
                    file_path.display()
                );
                continue;
            }
        };
        match apply(&mut fd, matches) {
            Ok(_) => {
                log::info!("Applied nmstate config: {}", file_path.display());
                if let Err(e) = relocate_file(&file_path) {
                    log::error!(
                        "Failed to rename applied state file: {} {}",
                        file_path.display(),
                        e
                    );
                }
            }
            Err(e) => {
                log::error!(
                    "Failed to apply state file {}: {}",
                    file_path.display(),
                    e
                );
            }
        }
    }

    Ok("".to_string())
}

// All file ending with `.yml` will be included.
fn get_config_files(folder: &str) -> Result<Vec<PathBuf>, CliError> {
    let folder = Path::new(folder);
    let mut ret = Vec::new();
    for entry in folder.read_dir()? {
        let file = entry?.path();
        if file.extension() == Some(OsStr::new(CONFIG_FILE_EXTENTION)) {
            ret.push(folder.join(file));
        }
    }
    ret.sort_unstable();
    Ok(ret)
}

// rename file by adding a suffix `.applied`.
fn relocate_file(file_path: &Path) -> Result<(), CliError> {
    let new_path = file_path.with_extension(RELOCATE_FILE_EXTENTION);
    std::fs::rename(file_path, &new_path)?;
    log::info!(
        "Renamed applied config {} to {}",
        file_path.display(),
        new_path.display()
    );
    Ok(())
}
