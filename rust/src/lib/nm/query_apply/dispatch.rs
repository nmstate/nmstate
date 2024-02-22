// SPDX-License-Identifier: Apache-2.0

use std::collections::hash_map::Entry;
use std::collections::HashMap;
use std::io::{Read, Write};
use std::os::unix::fs::OpenOptionsExt;

use crate::{
    DispatchConfig, ErrorKind, MergedInterfaces, MergedUserDefinedData,
    NmstateError, UserDefinedData, UserDefinedInterfaceType,
};

const DEFAULT_DISPATCH_DIR: &str = "/etc/NetworkManager/dispatcher.d";

const SCRIPT_START_COMMENT: &str = "## NMSTATE DISPATCH SCRIPT START";
const SCRIPT_END_COMMENT: &str = "## NMSTATE DISPATCH SCRIPT END";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum NmAction {
    Up,
    Down,
}

impl std::fmt::Display for NmAction {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::Up => "up",
                Self::Down => "down",
            }
        )
    }
}

pub(crate) fn apply_dispatch_script(
    merged_ifaces: &MergedInterfaces,
) -> Result<(), NmstateError> {
    for iface in merged_ifaces.kernel_ifaces.values().filter_map(|i| {
        if i.is_desired() {
            i.for_apply.as_ref()
        } else {
            None
        }
    }) {
        if iface.is_absent() {
            delete_dispatch_script(iface.name(), NmAction::Up)?;
            delete_dispatch_script(iface.name(), NmAction::Down)?;
        } else if let Some(dispatch_conf) = iface.base_iface().dispatch.as_ref()
        {
            let iface_name = iface.name();
            if let Some(post_up) = dispatch_conf.post_activation.as_deref() {
                if post_up.is_empty() {
                    delete_dispatch_script(iface_name, NmAction::Up)?;
                } else {
                    create_dispatch_script(iface_name, post_up, NmAction::Up)?;
                }
            }
            if let Some(post_down) = dispatch_conf.post_deactivation.as_deref()
            {
                if post_down.is_empty() {
                    delete_dispatch_script(iface_name, NmAction::Down)?;
                } else {
                    create_dispatch_script(
                        iface_name,
                        post_down,
                        NmAction::Down,
                    )?;
                }
            }
        }
    }
    Ok(())
}

fn create_dispatch_script(
    iface_name: &str,
    content: &str,
    nm_action: NmAction,
) -> Result<(), NmstateError> {
    let file_path = gen_file_path(iface_name, nm_action);
    let action_condition_line = match nm_action {
        NmAction::Up => r#"{ [ "$2" == "up" ] || [ "$2" == "reapply" ]; }"#,
        NmAction::Down => r#"[ "$2" == "down" ]"#,
    };

    let script_content = format!(
        r#"#!/usr/bin/bash
if [ "$1" == "{iface_name}" ] && {action_condition_line}; then
{SCRIPT_START_COMMENT}
{content}
{SCRIPT_END_COMMENT}
fi
"#
    );

    if let Err(e) =
        write_execute_file(file_path.as_str(), script_content.as_str())
    {
        return Err(NmstateError::new(
            ErrorKind::InvalidArgument,
            format!(
                "Failed to create NetworkManager dispatch script \
                {file_path}: {e}"
            ),
        ));
    }

    Ok(())
}

fn write_execute_file(file_path: &str, content: &str) -> std::io::Result<()> {
    let mut fd = std::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .mode(0o744)
        .open(file_path)?;
    fd.write_all(content.as_bytes())?;
    Ok(())
}

pub(crate) fn get_dispatches() -> HashMap<String, DispatchConfig> {
    let mut ret: HashMap<String, DispatchConfig> = HashMap::new();
    let dir = std::env::var("NMSTATE_NM_DISPATCH_DIR")
        .unwrap_or(DEFAULT_DISPATCH_DIR.to_string());

    if let Ok(fd) = std::fs::read_dir(&dir) {
        for entry in fd.filter_map(Result::ok) {
            let file_name = if let Ok(s) = entry.file_name().into_string() {
                if s.starts_with("nmstate-") {
                    s
                } else {
                    continue;
                }
            } else {
                continue;
            };
            let file_path = format!("{dir}/{file_name}");
            let parts: Vec<&str> = file_name.split('-').collect();
            if parts.len() == 3 {
                let iface_name = parts[1];
                if !["up.sh", "down.sh"].contains(&parts[2]) {
                    log::debug!("Got unknown dispatch action for {file_name}");
                    continue;
                }
                let script_content =
                    if let Some(s) = read_dispatch_script(&file_path) {
                        s
                    } else {
                        continue;
                    };
                let conf = match ret.entry(iface_name.to_string()) {
                    Entry::Occupied(o) => o.into_mut(),
                    Entry::Vacant(v) => v.insert(DispatchConfig::default()),
                };
                match parts[2] {
                    "up.sh" => conf.post_activation = Some(script_content),
                    "down.sh" => conf.post_deactivation = Some(script_content),
                    _ => (),
                }
            }
        }
    }
    ret
}

fn read_dispatch_script(file_path: &str) -> Option<String> {
    if let Ok(mut fd) = std::fs::File::open(file_path) {
        let mut script_content: Vec<&str> = Vec::new();
        let mut content = String::new();
        fd.read_to_string(&mut content).ok();
        let mut begin = false;
        for line in content.split('\n') {
            if begin {
                if line == SCRIPT_END_COMMENT {
                    break;
                } else {
                    script_content.push(line);
                }
            } else if line == SCRIPT_START_COMMENT {
                begin = true;
                continue;
            }
        }
        if !script_content.is_empty() {
            return Some(script_content.join("\n"));
        }
    }
    None
}

fn delete_dispatch_script(
    iface_name: &str,
    nm_action: NmAction,
) -> Result<(), NmstateError> {
    let file_path = gen_file_path(iface_name, nm_action);
    let path = std::path::Path::new(&file_path);

    if path.exists() {
        if let Err(e) = std::fs::remove_file(path) {
            return Err(NmstateError::new(
                ErrorKind::PermissionError,
                format!(
                    "Failed to remove dispatch script {file_path}, error: {e}"
                ),
            ));
        }
    }
    Ok(())
}

fn gen_file_path(iface_name: &str, nm_action: NmAction) -> String {
    let dir = std::env::var("NMSTATE_NM_DISPATCH_DIR")
        .unwrap_or(DEFAULT_DISPATCH_DIR.to_string());

    format!("{dir}/nmstate-{iface_name}-{nm_action}.sh")
}

fn gen_generic_file_path(iface_type_name: &str) -> String {
    let dir = std::env::var("NMSTATE_NM_DISPATCH_DIR")
        .unwrap_or(DEFAULT_DISPATCH_DIR.to_string());

    let path = format!("{dir}/device");

    if !std::path::Path::new(&path).exists() {
        // follow up write action will fail with proper error
        std::fs::create_dir(&path).ok();
    }

    format!("{dir}/device/{iface_type_name}")
}

pub(crate) fn get_user_defined_iface_types(
) -> Result<UserDefinedData, NmstateError> {
    let mut ret = UserDefinedData::default();
    let dir = std::env::var("NMSTATE_NM_DISPATCH_DIR")
        .unwrap_or(DEFAULT_DISPATCH_DIR.to_string());
    let dir = format!("{dir}/device");

    if std::path::Path::new(&dir).is_dir() {
        match std::fs::read_dir(&dir) {
            Ok(fd) => {
                let mut iface_types = Vec::new();
                for entry in fd.filter_map(|fd| fd.ok()) {
                    let file_name =
                        if let Ok(s) = entry.file_name().into_string() {
                            s
                        } else {
                            continue;
                        };
                    let file_path = format!("{dir}/{file_name}");
                    if let Some(conf) =
                        get_iface_type_conf(&file_name, &file_path)
                    {
                        iface_types.push(conf);
                    }
                }
                if !iface_types.is_empty() {
                    ret.interface_types = Some(iface_types);
                }
            }
            Err(e) => {
                log::info!("Failed to read {dir} {e}");
            }
        }
    }
    Ok(ret)
}

pub(crate) fn apply_user_defined_iface_type_scripts(
    user_defined: &MergedUserDefinedData,
) -> Result<(), NmstateError> {
    for (name, conf) in user_defined.desired.iter() {
        let path = gen_generic_file_path(name.as_str());
        if conf.is_absent() {
            log::info!("Removing user defined interface type {}", conf.name);
            let file_path = std::path::Path::new(&path);
            if file_path.exists() {
                std::fs::remove_file(&path).map_err(|e| {
                    NmstateError::new(
                        ErrorKind::PermissionError,
                        format!("Failed to remove file {path}: {e}"),
                    )
                })?
            };
        } else if let Some(content) = conf.handler_script.as_deref() {
            let mut fd = std::fs::OpenOptions::new()
                .create(true)
                .write(true)
                .truncate(true)
                .mode(0o744)
                .open(&path)
                .map_err(|e| {
                    NmstateError::new(
                        ErrorKind::PermissionError,
                        format!("Failed to write file {path}: {e}"),
                    )
                })?;
            fd.write_all(content.as_bytes()).map_err(|e| {
                NmstateError::new(
                    ErrorKind::PermissionError,
                    format!("Failed to write file {path}: {e}"),
                )
            })?;
        }
    }
    Ok(())
}

fn get_iface_type_conf(
    file_name: &str,
    file_path: &str,
) -> Option<UserDefinedInterfaceType> {
    if let Ok(mut fd) = std::fs::File::open(file_path) {
        let mut content = String::new();
        fd.read_to_string(&mut content).ok();
        if !content.is_empty() {
            return Some(UserDefinedInterfaceType {
                name: file_name.to_string(),
                handler_script: Some(content),
                ..Default::default()
            });
        }
    }
    None
}
