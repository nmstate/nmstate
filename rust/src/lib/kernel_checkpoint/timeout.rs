// SPDX-License-Identifier: Apache-2.0

use std::fs;
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::Duration;

use nix::sys::signal::{Signal, kill};
use nix::unistd::{ForkResult, Pid, fork, setsid};

use crate::{ErrorKind, NmstateError};

const PID_FILE_EXTENSION: &str = "pid";

fn get_pid_file_path(checkpoint_path: &PathBuf) -> PathBuf {
    checkpoint_path.with_extension(PID_FILE_EXTENSION)
}

/// Spawn a detached watchdog process that will rollback the checkpoint
/// after the specified timeout (in seconds).
///
/// The watchdog:
/// 1. Forks and detaches from the parent process (setsid)
/// 2. Sleeps for `timeout_secs` (sync, no tokio)
/// 3. If checkpoint file still exists, exec's `nmstatectl rollback`
///    as a fresh process (avoids tokio-after-fork issues)
/// 4. Cleans up and exits
///
/// The watchdog PID is stored alongside the checkpoint file for
/// cancellation on commit.
pub(crate) fn spawn_timeout_watchdog(
    checkpoint_id: &str,
    checkpoint_path: &PathBuf,
    timeout_secs: u32,
) -> Result<(), NmstateError> {
    let checkpoint_id_owned = checkpoint_id.to_string();
    let checkpoint_path_owned = checkpoint_path.clone();

    // Resolve current executable path before fork
    let exe_path = std::env::current_exe().map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!("Failed to resolve current executable: {}", e),
        )
    })?;

    // SAFETY: fork() is safe here because the child only performs
    // async-signal-safe operations (sleep, file checks) and then
    // exec's a fresh process for the actual rollback work.
    match unsafe { fork() } {
        Ok(ForkResult::Parent { child }) => {
            // Store child PID for later cancellation
            let pid_path = get_pid_file_path(&checkpoint_path_owned);
            if let Err(e) = write_pid_file(&pid_path, child) {
                log::warn!(
                    "Failed to write watchdog PID file {}: {}",
                    pid_path.display(),
                    e
                );
            }
            log::info!(
                "Spawned timeout watchdog (PID {}) for checkpoint {}, \
                 rollback in {}s",
                child,
                checkpoint_id,
                timeout_secs
            );
            Ok(())
        }
        Ok(ForkResult::Child) => {
            // Detach from parent session
            let _ = setsid();

            // Redirect stdio to /dev/null
            close_stdio();

            // Run the watchdog: sleep then exec rollback
            run_watchdog(
                &checkpoint_id_owned,
                &checkpoint_path_owned,
                &exe_path,
                timeout_secs,
            );

            std::process::exit(0);
        }
        Err(e) => {
            log::warn!(
                "Failed to fork timeout watchdog for checkpoint {}: {}",
                checkpoint_id,
                e
            );
            Err(NmstateError::new(
                ErrorKind::Bug,
                format!("Failed to fork timeout watchdog: {}", e),
            ))
        }
    }
}

/// Cancel a running timeout watchdog by killing the process and
/// removing the PID file.
pub(crate) fn cancel_timeout_watchdog(checkpoint_path: &PathBuf) {
    let pid_path = get_pid_file_path(checkpoint_path);

    if let Some(pid) = read_pid_file(&pid_path) {
        match kill(pid, Signal::SIGTERM) {
            Ok(()) => {
                log::info!("Cancelled timeout watchdog (PID {})", pid);
            }
            Err(nix::errno::Errno::ESRCH) => {
                // Process already gone, that's fine
                log::debug!("Timeout watchdog (PID {}) already exited", pid);
            }
            Err(e) => {
                log::warn!(
                    "Failed to kill timeout watchdog (PID {}): {}",
                    pid,
                    e
                );
            }
        }
    }

    // Clean up PID file
    if pid_path.exists() {
        if let Err(e) = fs::remove_file(&pid_path) {
            log::warn!(
                "Failed to remove PID file {}: {}",
                pid_path.display(),
                e
            );
        }
    }
}

/// Watchdog logic: sleep, then exec nmstatectl rollback.
/// Only uses sync operations - no tokio after fork.
fn run_watchdog(
    checkpoint_id: &str,
    checkpoint_path: &PathBuf,
    exe_path: &PathBuf,
    timeout_secs: u32,
) {
    // Sleep for the timeout duration (sync, no tokio)
    std::thread::sleep(Duration::from_secs(timeout_secs as u64));

    // Check if checkpoint file still exists (commit removes it)
    if !checkpoint_path.exists() {
        // Checkpoint was committed, nothing to do
        return;
    }

    // Exec nmstatectl rollback as a fresh process.
    // This avoids tokio-after-fork corruption by starting a clean
    // process with its own runtime.
    let result = Command::new(exe_path)
        .arg("rollback")
        .arg(checkpoint_id)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();

    match result {
        Ok(status) => {
            if !status.success() {
                watchdog_log(
                    checkpoint_path,
                    &format!(
                        "nmstatectl rollback exited with status: {}",
                        status
                    ),
                );
            }
        }
        Err(e) => {
            watchdog_log(
                checkpoint_path,
                &format!("Failed to exec nmstatectl rollback: {}", e),
            );
        }
    }

    // Clean up PID file
    let pid_path = get_pid_file_path(checkpoint_path);
    let _ = fs::remove_file(&pid_path);
}

fn watchdog_log(checkpoint_path: &PathBuf, msg: &str) {
    let log_path = checkpoint_path.with_extension("log");
    if let Ok(mut f) =
        fs::OpenOptions::new().create(true).append(true).open(&log_path)
    {
        let _ = writeln!(f, "{}", msg);
    }
}

fn write_pid_file(path: &PathBuf, pid: Pid) -> Result<(), NmstateError> {
    let mut file = fs::File::create(path).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!(
                "Failed to create PID file {}: {}",
                path.display(),
                e
            ),
        )
    })?;
    file.write_all(pid.to_string().as_bytes()).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!(
                "Failed to write PID file {}: {}",
                path.display(),
                e
            ),
        )
    })?;
    Ok(())
}

fn read_pid_file(path: &PathBuf) -> Option<Pid> {
    fs::read_to_string(path)
        .ok()
        .and_then(|s| s.trim().parse::<i32>().ok())
        .map(Pid::from_raw)
}

fn close_stdio() {
    if let Ok(devnull) = fs::File::open("/dev/null") {
        use std::os::unix::io::AsRawFd;
        let devnull_fd = devnull.as_raw_fd();
        unsafe {
            libc::dup2(devnull_fd, libc::STDIN_FILENO);
            libc::dup2(devnull_fd, libc::STDOUT_FILENO);
            libc::dup2(devnull_fd, libc::STDERR_FILENO);
        }
    }
}
