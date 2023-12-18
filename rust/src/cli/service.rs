// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;
use std::ffi::OsStr;
use std::fmt;
use std::fs;
use std::fs::File;
use std::io::{BufReader, Read};
use std::path::{Path, PathBuf};

use crate::{apply::apply, error::CliError};

use ring::digest::{Context, SHA256};

const CONFIG_FILE_EXTENTION: &str = "yml";
const CHECKSUM_FILE_EXTENTION: &str = "applied";

#[derive(Eq, Hash, PartialEq, Clone, PartialOrd, Ord)]
struct FileChecksum {
    path: PathBuf,
    checksum: String,
}

impl FileChecksum {
    fn new(path: PathBuf, checksum: String) -> Self {
        Self { path, checksum }
    }
}

struct HexSlice<'a>(&'a [u8]);

impl<'a> fmt::Display for HexSlice<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for &byte in self.0 {
            write!(f, "{:0>2x}", byte)?;
        }
        Ok(())
    }
}

pub(crate) fn ncl_service(
    matches: &clap::ArgMatches,
) -> Result<String, CliError> {
    let folder = matches
        .value_of(crate::CONFIG_FOLDER_KEY)
        .unwrap_or(crate::DEFAULT_SERVICE_FOLDER);

    let config_files = match get_config_files(folder) {
        Ok(f) => f,
        Err(e) => {
            log::info!(
                "Failed to read config folder {folder} due to \
                error {e}, ignoring"
            );
            return Ok(String::new());
        }
    };
    if config_files.is_empty() {
        log::info!(
            "No new nmstate config(end with .{}) found in config folder {}",
            CONFIG_FILE_EXTENTION,
            folder
        );
        return Ok(String::new());
    }

    // Due to bug of NetworkManager, the `After=NetworkManager.service` in
    // `nmstate.service` cannot guarantee the ready of NM dbus.
    // We sleep for 2 seconds here to avoid meaningless retry.
    std::thread::sleep(std::time::Duration::from_secs(2));

    for config_file in config_files {
        let mut fd = match std::fs::File::open(&config_file.path) {
            Ok(fd) => fd,
            Err(e) => {
                log::error!(
                    "Failed to read config file {}: {e}",
                    config_file.path.display()
                );
                continue;
            }
        };
        match apply(&mut fd, matches) {
            Ok(_) => {
                log::info!(
                    "Applied nmstate config: {}",
                    config_file.path.display()
                );
                if let Err(e) =
                    write_checksum(&config_file.path, &config_file.checksum)
                {
                    log::error!(
                        "Failed to generate checksum file: {} {}",
                        config_file.path.display(),
                        e
                    );
                }
            }
            Err(e) => {
                log::error!(
                    "Failed to apply state file {}: {}",
                    config_file.path.display(),
                    e
                );
            }
        }
    }

    Ok("".to_string())
}

// All file ending with `.yml` that do not have a sha256 checksum stored at
// a `.applied` file or the checksum stored differs.
fn get_config_files(folder: &str) -> Result<Vec<FileChecksum>, CliError> {
    let folder = Path::new(folder);
    let mut yml_files = HashSet::<FileChecksum>::new();
    let mut applied_files = HashSet::<FileChecksum>::new();
    for entry in folder.read_dir()? {
        let file = entry?.path();
        if file.extension() == Some(OsStr::new(CONFIG_FILE_EXTENTION)) {
            let digest = sha256_digest(&file)?;
            yml_files.insert(FileChecksum::new(
                folder.join(file).with_extension(""),
                digest,
            ));
        } else if file.extension() == Some(OsStr::new(CHECKSUM_FILE_EXTENTION))
        {
            let digest = fs::read_to_string(&file)?;
            applied_files.insert(FileChecksum::new(
                folder.join(file).with_extension(""),
                digest,
            ));
        }
    }
    let mut ret: Vec<_> = yml_files
        .difference(&applied_files)
        .cloned()
        .map(|f| {
            FileChecksum::new(
                f.path.with_extension(CONFIG_FILE_EXTENTION),
                f.checksum,
            )
        })
        .collect();
    ret.sort_by_key(|f| f.path.clone());
    Ok(ret)
}

// Dump state checksum to `.applied` file.
pub(crate) fn write_checksum(
    file_path: &Path,
    checksum: &str,
) -> Result<(), CliError> {
    let checksum_file_path = file_path.with_extension(CHECKSUM_FILE_EXTENTION);
    fs::write(&checksum_file_path, checksum)?;
    log::info!(
        "Checksum for config {} stored at {}",
        file_path.display(),
        checksum_file_path.display(),
    );
    Ok(())
}

fn sha256_digest(file_path: &PathBuf) -> Result<String, CliError> {
    let mut context = Context::new(&SHA256);
    let mut buffer = [0; 1024];

    let input = File::open(file_path)?;
    let mut reader = BufReader::new(input);

    loop {
        let count = reader.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        context.update(&buffer[..count]);
    }

    Ok(format!("{}", HexSlice(context.finish().as_ref())))
}
