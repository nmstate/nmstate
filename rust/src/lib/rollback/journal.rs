// SPDX-License-Identifier: Apache-2.0

use std::{
    fs::{File, OpenOptions},
    io::{Read, Write},
    os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt},
    path::{Path, PathBuf},
};

use serde::{Deserialize, Serialize};

use super::{RouteRuleRemoval, failure, permission};
use crate::{NmstateError, nm::RuleCheckpointConnections};

pub(super) const DIRECTORY: &str = "/run/nmstate/rollback";
const VERSION: u32 = 1;
const MAX_JOURNAL_BYTES: u64 = 64 * 1024 * 1024;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub(super) struct Namespace {
    device: u64,
    inode: u64,
}

impl Namespace {
    pub fn read(path: impl AsRef<Path>) -> Result<Self, NmstateError> {
        let metadata = std::fs::metadata(path.as_ref())
            .map_err(|e| failure(format!("Cannot inspect namespace: {e}")))?;
        Ok(Self {
            device: metadata.dev(),
            inode: metadata.ino(),
        })
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub(super) struct Identity {
    pub boot: String,
    pub namespace: Namespace,
    pub user_namespace: Namespace,
    pub nm_owner: String,
    pub bus_id: String,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub(super) enum Phase {
    Preparing,
    Applying,
    Pending,
    Commit,
    Rollback,
    Unresolved(String),
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct RuleStep {
    pub removal: RouteRuleRemoval,
    pub restoration: Option<RouteRuleRemoval>,
    pub restored: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Journal {
    version: u32,
    pub identity: Identity,
    pub checkpoint: String,
    pub phase: Phase,
    pub deadline_ms: Option<u64>,
    pub nm_finished: bool,
    pub connections: RuleCheckpointConnections,
    pub initial_rules: Option<RouteRuleRemoval>,
    pub rules: Vec<RuleStep>,
}

impl Journal {
    pub fn new(
        identity: Identity,
        checkpoint: String,
        deadline_ms: Option<u64>,
        connections: RuleCheckpointConnections,
        initial_rules: Option<RouteRuleRemoval>,
    ) -> Self {
        Self {
            version: VERSION,
            identity,
            checkpoint,
            phase: Phase::Preparing,
            deadline_ms,
            nm_finished: false,
            connections,
            initial_rules,
            rules: Vec::new(),
        }
    }

    pub fn matches(&self, checkpoint: &str) -> bool {
        checkpoint.is_empty() || checkpoint == self.checkpoint
    }

    pub fn validate(&self) -> Result<(), NmstateError> {
        if self.version != VERSION
            || !self
                .checkpoint
                .starts_with("/org/freedesktop/NetworkManager/Checkpoint/")
            || self.identity.boot.trim().is_empty()
            || !self.identity.nm_owner.starts_with(':')
            || self.identity.bus_id.is_empty()
            || (self.initial_rules.is_none() && !self.rules.is_empty())
        {
            return Err(failure(
                "Invalid rollback journal identity or version",
            ));
        }
        Ok(())
    }
}

#[derive(Clone)]
pub(super) struct Store {
    directory: PathBuf,
}

impl Store {
    pub fn new() -> Self {
        Self {
            directory: DIRECTORY.into(),
        }
    }

    #[cfg(test)]
    fn at(directory: PathBuf) -> Self {
        Self { directory }
    }

    fn path(&self) -> PathBuf {
        self.directory.join("transaction.json")
    }

    pub fn load(&self) -> Result<Option<Journal>, NmstateError> {
        let mut file = match protected_open(&self.path(), false) {
            Ok(f) => f,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                return Ok(None);
            }
            Err(e) => return Err(failure(format!("Cannot read journal: {e}"))),
        };
        check_file(&file)?;
        let mut data = Vec::new();
        (&mut file)
            .take(MAX_JOURNAL_BYTES + 1)
            .read_to_end(&mut data)
            .map_err(|e| failure(format!("Cannot read journal: {e}")))?;
        if data.len() as u64 > MAX_JOURNAL_BYTES {
            return Err(failure("Rollback journal exceeds its size limit"));
        }
        let journal: Journal = serde_json::from_slice(&data)
            .map_err(|e| failure(format!("Invalid rollback journal: {e}")))?;
        journal.validate()?;
        Ok(Some(journal))
    }

    pub fn save(&self, journal: &Journal) -> Result<(), NmstateError> {
        journal.validate()?;
        let data = serde_json::to_vec(journal)
            .map_err(|e| failure(format!("Cannot encode journal: {e}")))?;
        if data.len() as u64 > MAX_JOURNAL_BYTES {
            return Err(failure("Rollback journal exceeds its size limit"));
        }
        let temporary = self.directory.join("transaction.json.new");
        let mut file = protected_open(&temporary, true)
            .map_err(|e| failure(format!("Cannot write journal: {e}")))?;
        check_file(&file)?;
        file.set_len(0)
            .and_then(|()| file.write_all(&data))
            .and_then(|()| file.sync_all())
            .map_err(|e| failure(format!("Cannot persist journal: {e}")))?;
        std::fs::rename(temporary, self.path())
            .map_err(|e| failure(format!("Cannot replace journal: {e}")))?;
        self.sync_directory()
    }

    pub fn clear(&self) -> Result<(), NmstateError> {
        match std::fs::remove_file(self.path()) {
            Ok(()) => self.sync_directory(),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(e) => Err(failure(format!("Cannot remove journal: {e}"))),
        }
    }

    fn sync_directory(&self) -> Result<(), NmstateError> {
        File::open(&self.directory)
            .and_then(|file| file.sync_all())
            .map_err(|e| failure(format!("Cannot sync journal directory: {e}")))
    }
}

fn protected_open(path: &Path, write: bool) -> std::io::Result<File> {
    OpenOptions::new()
        .read(true)
        .write(write)
        .create(write)
        .mode(0o600)
        .custom_flags(nix::libc::O_NOFOLLOW | nix::libc::O_CLOEXEC)
        .open(path)
}

fn check_file(file: &File) -> Result<(), NmstateError> {
    let metadata = file
        .metadata()
        .map_err(|e| failure(format!("Cannot inspect journal: {e}")))?;
    if !metadata.is_file()
        || metadata.uid() != 0
        || metadata.nlink() != 1
        || metadata.permissions().mode() & 0o077 != 0
    {
        return Err(permission(
            "Rollback journal must be a private root-owned file",
        ));
    }
    Ok(())
}

pub(super) fn check_directory(path: &Path) -> Result<(), NmstateError> {
    let metadata = std::fs::symlink_metadata(path).map_err(|e| {
        failure(format!("Cannot inspect {}: {e}", path.display()))
    })?;
    if !metadata.is_dir()
        || metadata.uid() != 0
        || metadata.permissions().mode() & 0o022 != 0
    {
        return Err(permission(format!(
            "{} must be a root-owned directory without group or other write \
             access",
            path.display()
        )));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn journal() -> Journal {
        Journal::new(
            Identity {
                boot: "test-boot".into(),
                namespace: Namespace {
                    device: 1,
                    inode: 2,
                },
                user_namespace: Namespace {
                    device: 1,
                    inode: 3,
                },
                nm_owner: ":1.42".into(),
                bus_id: "test-bus".into(),
            },
            "/org/freedesktop/NetworkManager/Checkpoint/7".into(),
            Some(1234),
            RuleCheckpointConnections::default(),
            None,
        )
    }

    #[test]
    fn unknown_version_cannot_be_recovered() {
        let mut record = journal();
        record.version += 1;
        assert!(record.validate().is_err());
    }

    #[test]
    fn recovery_record_keeps_decision_and_identity() {
        let mut record = journal();
        record.phase = Phase::Rollback;
        record.nm_finished = true;
        let decoded: Journal =
            serde_json::from_slice(&serde_json::to_vec(&record).unwrap())
                .unwrap();
        assert_eq!(decoded.identity, record.identity);
        assert_eq!(decoded.phase, Phase::Rollback);
        assert!(decoded.nm_finished);
        assert_eq!(decoded.deadline_ms, Some(1234));
        assert!(
            !decoded.matches("/org/freedesktop/NetworkManager/Checkpoint/8")
        );
        assert!(
            decoded.matches("/org/freedesktop/NetworkManager/Checkpoint/7")
        );
        assert!(decoded.matches(""));
    }

    #[test]
    fn malformed_record_cannot_be_recovered() {
        let mut record = journal();
        record.checkpoint = "/tmp/7".into();
        assert!(record.validate().is_err());

        let mut record = journal();
        record.identity.nm_owner = "1.42".into();
        assert!(record.validate().is_err());
    }

    #[test]
    fn missing_journal_loads_as_empty() {
        let store =
            Store::at(std::env::temp_dir().join(format!(
                "nmstate-journal-missing-{}",
                std::process::id()
            )));
        assert!(store.load().unwrap().is_none());
    }

    #[test]
    fn unprivileged_journal_is_rejected() {
        if std::fs::metadata("/proc/self").unwrap().uid() == 0 {
            return;
        }
        let directory = std::env::temp_dir()
            .join(format!("nmstate-journal-user-{}", std::process::id()));
        std::fs::create_dir_all(&directory).unwrap();
        let store = Store::at(directory.clone());
        std::fs::write(store.path(), b"{}").unwrap();
        std::fs::set_permissions(
            store.path(),
            std::fs::Permissions::from_mode(0o600),
        )
        .unwrap();
        let result = store.load();
        std::fs::remove_dir_all(&directory).unwrap();
        assert_eq!(
            result.unwrap_err().kind(),
            crate::ErrorKind::PermissionError
        );
    }
}
