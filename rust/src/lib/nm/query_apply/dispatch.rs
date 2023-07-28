// SPDX-License-Identifier: Apache-2.0

use std::collections::hash_map::Entry;
use std::collections::HashMap;
use std::io::{Read, Write};
use std::os::unix::fs::OpenOptionsExt;

use crate::{DispatchConfig, ErrorKind, MergedInterfaces, NmstateError};

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
        if let Some(dispatch_conf) = iface.base_iface().dispatch.as_ref() {
            let iface_name = iface.name();
            if let Some(post_up) = dispatch_conf.post_activation.as_deref() {
                create_dispatch_script(iface_name, post_up, NmAction::Up)?
            }
            if let Some(post_down) = dispatch_conf.post_deactivation.as_deref()
            {
                create_dispatch_script(iface_name, post_down, NmAction::Down)?
            }
        }
    }
    Ok(())
}

// Create dispatch script with file path as:
//      /etc/NetworkManager/dispatcher.d/nmstate-eth1-up.sh
//      /etc/networkmanager/dispatcher.d/nmstate-ovs1-down.sh
fn create_dispatch_script(
    iface_name: &str,
    content: &str,
    nm_action: NmAction,
) -> Result<(), NmstateError> {
    let dir = std::env::var("NMSTATE_NM_DISPATCH_DIR")
        .unwrap_or(DEFAULT_DISPATCH_DIR.to_string());

    let file_path = format!("{dir}/nmstate-{iface_name}-{nm_action}.sh");
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
