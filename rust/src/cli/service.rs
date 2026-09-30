// SPDX-License-Identifier: Apache-2.0

use std::{
    collections::HashSet,
    ffi::OsStr,
    fs,
    io::Read,
    path::{Path, PathBuf},
};

use serde::Deserialize;

use crate::{apply::apply_state, error::CliError, state::state_from_fd};

const CONFIG_FILE_EXTENSION: &str = "yml";
const CONFIG_FILE_EXTENSION2: &str = "yaml";
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
    let folder = matches
        .get_one::<String>(crate::CONFIG_FOLDER_KEY)
        .map(String::as_str)
        .unwrap_or(crate::DEFAULT_SERVICE_FOLDER);

    let config = load_config(folder)?;

    if !Path::new(&folder).exists() {
        log::info!("{folder} does not exist, skipping");
        return Ok(String::new());
    }

    let state_files = get_unapplied_state_files(
        folder,
        config.service.keep_state_file_after_apply,
    )?;
    if state_files.is_empty() {
        log::info!(
            "No new nmstate config(end with .{CONFIG_FILE_EXTENSION} or \
             .{CONFIG_FILE_EXTENSION2}) found in config folder {folder}"
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
            #[allow(deprecated)]
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
    let mut yml_files = HashSet::<FileContent>::new();
    let mut yml_file_names = HashSet::<PathBuf>::new();
    let mut applied_files = HashSet::<FileContent>::new();
    for entry in folder.read_dir()? {
        let file = entry?.path();
        if file.extension() == Some(OsStr::new(CONFIG_FILE_EXTENSION))
            || file.extension() == Some(OsStr::new(CONFIG_FILE_EXTENSION2))
        {
            let content = fs::read_to_string(&file)?;
            let file_name_no_extention = folder.join(&file).with_extension("");
            if !yml_file_names.insert(file_name_no_extention.clone()) {
                return Err(CliError::from(format!(
                    "Conflict YAML file {}.yml and {}.yaml",
                    file_name_no_extention.display(),
                    file_name_no_extention.display(),
                )));
            }
            yml_files.insert(FileContent::new(file_name_no_extention, content));
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

    let mut ret: Vec<FileContent> = Vec::new();
    for fc in yml_files.difference(&applied_files) {
        let file_path =
            if fc.path.with_extension(CONFIG_FILE_EXTENSION).exists() {
                fc.path.with_extension(CONFIG_FILE_EXTENSION)
            } else if fc.path.with_extension(CONFIG_FILE_EXTENSION2).exists() {
                fc.path.with_extension(CONFIG_FILE_EXTENSION2)
            } else {
                log::error!(
                    "Bug: {}.yml or {}.yaml not exists",
                    fc.path.display(),
                    fc.path.display()
                );
                continue;
            };

        ret.push(FileContent::new(file_path, fc.content.clone()));
    }

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

#[cfg(test)]
mod tests {
    use super::*;

    struct TestDir(PathBuf);

    impl TestDir {
        fn new() -> Self {
            let path = std::env::temp_dir()
                .join(format!("nmstate-service-{}", uuid::Uuid::new_v4()));
            fs::create_dir(&path).unwrap();
            Self(path)
        }

        fn write(&self, name: &str, content: &str) {
            fs::write(self.0.join(name), content).unwrap();
        }

        fn collect(&self, keep: bool) -> Result<Vec<FileContent>, CliError> {
            get_unapplied_state_files(self.0.to_str().unwrap(), keep)
        }
    }

    impl Drop for TestDir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn test_conflicting_yaml_extensions() {
        for keep in [false, true] {
            for yaml_content in ["interfaces: []", "dns-resolver: {}"] {
                let dir = TestDir::new();
                dir.write("state.yml", "interfaces: []");
                dir.write("state.yaml", yaml_content);
                dir.write("state.applied", "interfaces: []");

                let err = dir
                    .collect(keep)
                    .err()
                    .expect("colliding YAML basenames must fail");
                assert_eq!(err.code, crate::error::DEFAULT_ERROR_CODE);
                assert_eq!(
                    err.error_msg,
                    format!(
                        "Conflict YAML file {}.yml and {}.yaml",
                        dir.0.join("state").display(),
                        dir.0.join("state").display(),
                    )
                );
            }
        }
    }

    #[test]
    fn test_distinct_yaml_files_with_identical_contents() {
        for keep in [false, true] {
            let dir = TestDir::new();
            dir.write("b.yaml", "interfaces: []");
            dir.write("a.yml", "interfaces: []");

            let files = dir.collect(keep).unwrap();
            assert_eq!(
                files
                    .iter()
                    .map(|file| (file.path.clone(), file.content.as_str()))
                    .collect::<Vec<_>>(),
                vec![
                    (dir.0.join("a.yml"), "interfaces: []"),
                    (dir.0.join("b.yaml"), "interfaces: []"),
                ]
            );
        }
    }

    #[test]
    fn test_applied_content_change_detection() {
        for extension in ["yml", "yaml"] {
            let dir = TestDir::new();
            let name = format!("state.{extension}");
            dir.write(&name, "interfaces: []");
            dir.write("state.applied", "interfaces: []");
            assert!(dir.collect(true).unwrap().is_empty());

            let files = dir.collect(false).unwrap();
            assert_eq!(files.len(), 1);
            assert_eq!(files[0].path, dir.0.join(&name));
            assert_eq!(files[0].content, "interfaces: []");

            dir.write(&name, "dns-resolver: {}");
            let files = dir.collect(true).unwrap();
            assert_eq!(files.len(), 1);
            assert_eq!(files[0].path, dir.0.join(&name));
            assert_eq!(files[0].content, "dns-resolver: {}");
        }
    }
}
