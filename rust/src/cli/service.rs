// SPDX-License-Identifier: Apache-2.0

use std::ffi::OsStr;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use nmstate::{InterfaceType, NetworkState};

use crate::{apply::apply, error::CliError};

const CONFIG_FILE_EXTENTION: &str = "yml";
const RELOCATE_FILE_EXTENTION: &str = "applied";
const PIN_IFACE_NAME_FOLDER: &str = "pin_iface_name";
const PIN_STATE_FILENAME: &str = "pin.yml";
const SYSTEMD_NETWORK_LINK_FOLDER: &str = "/etc/systemd/network";

pub(crate) fn ncl_service(
    matches: &clap::ArgMatches,
) -> Result<String, CliError> {
    let folder = matches
        .value_of(crate::CONFIG_FOLDER_KEY)
        .unwrap_or(crate::DEFAULT_SERVICE_FOLDER);

    let pin_iface_name_dir = format!("{folder}/{PIN_IFACE_NAME_FOLDER}");
    let pin_iface_path = Path::new(&pin_iface_name_dir);
    if pin_iface_path.exists() {
        pin_iface_name(&pin_iface_path)?;
    }

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
            "No nmstate config(end with .{}) found in config folder {}",
            CONFIG_FILE_EXTENTION,
            folder
        );
        return Ok(String::new());
    }

    // Due to bug of NetworkManager, the `After=NetworkManager.service` in
    // `nmstate.service` cannot guarantee the ready of NM dbus.
    // We sleep for 2 seconds here to avoid meaningless retry.
    std::thread::sleep(std::time::Duration::from_secs(2));

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

fn pin_iface_name(cfg_dir: &Path) -> Result<(), CliError> {
    let file_path = cfg_dir.join(PIN_STATE_FILENAME);
    let mut fd = std::fs::File::open(&file_path)?;
    let mut content = String::new();
    fd.read_to_string(&mut content)?;
    let pin_state: NetworkState = serde_yaml::from_str(&content)?;
    let mut cur_state = NetworkState::new();
    cur_state.set_kernel_only(true);
    cur_state.set_running_config_only(true);
    cur_state.retrieve()?;

    for cur_iface in cur_state
        .interfaces
        .iter()
        .filter(|i| i.iface_type() == InterfaceType::Ethernet)
    {
        let cur_mac = match cur_iface.base_iface().mac_address.as_ref() {
            Some(c) => c,
            None => continue,
        };
        if pin_state
            .interfaces
            .get_iface(cur_iface.name(), cur_iface.iface_type())
            .is_none()
        {
            for pin_iface in pin_state
                .interfaces
                .iter()
                .filter(|i| i.iface_type() == InterfaceType::Ethernet)
            {
                if pin_iface.base_iface().mac_address.as_ref() == Some(cur_mac)
                    && pin_iface.name() != cur_iface.name()
                {
                    log::info!(
                        "Pining the interface with MAC {cur_mac} to \
                        interface name {}",
                        pin_iface.name()
                    );
                    pin_iface_name_via_systemd_link(cur_mac, pin_iface.name())?;
                }
            }
        }
    }

    relocate_file(&file_path)?;
    Ok(())
}

fn pin_iface_name_via_systemd_link(
    mac: &str,
    iface_name: &str,
) -> Result<(), CliError> {
    let link_dir = Path::new(SYSTEMD_NETWORK_LINK_FOLDER);
    if !link_dir.exists() {
        std::fs::create_dir(&link_dir)?;
    }

    let content =
        format!("[Match]\nMACAddress={mac}\n\n[Link]\nName={iface_name}\n");

    // 98 here is important as it should be invoked after others but before
    // 99-default.link
    let file_path = link_dir.join(format!("98-{iface_name}.link"));

    let mut fd = std::fs::OpenOptions::new()
        .write(true)
        .truncate(true)
        .create(true)
        .open(&file_path)
        .map_err(|e| {
            CliError::from(format!(
                "Failed to store captured states to file {}: {e}",
                file_path.display()
            ))
        })?;
    fd.write_all(content.as_bytes())?;
    log::info!(
        "Systemd network link file created at {}",
        file_path.display()
    );
    Ok(())
}
