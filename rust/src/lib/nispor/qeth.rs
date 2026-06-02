// SPDX-License-Identifier: Apache-2.0
//
// sysfs_qeth_vnicc.rs — Low-level sysfs read/write for qeth vnicc attributes.
//
// All public functions in this module guard against non-s390x at runtime so
// that the same binary can be cross-compiled or run under an emulator for
// testing purposes.  The compile-time cfg(target_arch = "s390x") gates are
// used only for the sysfs path helper; the rest of the logic is arch-agnostic.

use std::fs;
use std::path::{Path, PathBuf};

use crate::ifaces::qeth_vnicc::VniccConfig;
use crate::{ErrorKind, NmstateError};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const QETH_SYSFS_BASE: &str = "/sys/bus/ccwgroup/devices";
const VNICC_SUBDIR: &str = "vnicc";

// Attribute names must match the kernel sysfs names exactly.
const ATTR_FLOODING: &str = "flooding";
const ATTR_MCAST_FLOODING: &str = "mcast_flooding";
const ATTR_RX_BCAST: &str = "rx_bcast";
const ATTR_LEARNING: &str = "learning";
const ATTR_LEARNING_TIMEOUT: &str = "learning_timeout";
const ATTR_TAKEOVER_LEARNING: &str = "takeover_learning";
const ATTR_TAKEOVER_SETVMAC: &str = "takeover_setvmac";
const ATTR_BRIDGE_INVISIBLE: &str = "bridge_invisible";

// ---------------------------------------------------------------------------
// Architecture guard
// ---------------------------------------------------------------------------

/// Returns an error if the running kernel is not s390x.
///
/// We detect this via `/proc/version` rather than a compile-time cfg so that
/// integration tests compiled for x86_64 can at least exercise the error path.
fn require_s390x() -> Result<(), NmstateError> {
    #[cfg(target_arch = "s390x")]
    {
        return Ok(());
    }

    // Fallback for non-s390x: check /proc/version (useful in cross-tests).
    #[cfg(not(target_arch = "s390x"))]
    {
        let version = fs::read_to_string("/proc/version").unwrap_or_default();
        if version.contains("s390x") || version.contains("s390") {
            return Ok(());
        }
        return Err(NmstateError::new(
            ErrorKind::NotImplementedError,
            "qeth vnicc configuration is only supported on s390x architecture"
                .to_string(),
        ));
    }

    #[allow(unreachable_code)]
    Ok(())
}

// ---------------------------------------------------------------------------
// Sysfs path helpers
// ---------------------------------------------------------------------------

/// Returns the sysfs `vnicc/` directory for the given interface name.
///
/// The mapping from *interface name* (e.g. `eth0`) to *bus-id* (e.g.
/// `0.0.a016`) is resolved by reading the `if_name` symlink target or by
/// iterating `/sys/bus/ccwgroup/devices/` until a match is found.
///
/// On a real IBM Z node `lsqeth` uses the same traversal.
fn vnicc_dir_for_iface(iface_name: &str) -> Result<PathBuf, NmstateError> {
    let base = Path::new(QETH_SYSFS_BASE);

    // Walk every ccwgroup device and check its net/<iface_name> child.
    let entries = fs::read_dir(base).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!("Cannot enumerate qeth devices at {QETH_SYSFS_BASE}: {e}"),
        )
    })?;

    for entry in entries.flatten() {
        let bus_path = entry.path();
        // Each qeth device exposes its network interface name under
        // <bus_path>/net/<iface_name>/ (a directory, one per interface).
        let net_dir = bus_path.join("net").join(iface_name);
        if net_dir.is_dir() {
            let vnicc = bus_path.join(VNICC_SUBDIR);
            if vnicc.is_dir() {
                return Ok(vnicc);
            } else {
                return Err(NmstateError::new(
                    ErrorKind::NotImplementedError,
                    format!(
                        "Interface {iface_name} is a qeth device but has no \
                         vnicc sysfs directory; driver may not support vnicc"
                    ),
                ));
            }
        }
    }

    Err(NmstateError::new(
        ErrorKind::InvalidArgument,
        format!(
            "No qeth device found for interface {iface_name}; \
             vnicc is only supported on qeth (OSA/HiperSockets) devices"
        ),
    ))
}

/// Build the full path to one vnicc attribute file.
fn attr_path(vnicc_dir: &Path, attr: &str) -> PathBuf {
    vnicc_dir.join(attr)
}

// ---------------------------------------------------------------------------
// Primitive read / write helpers
// ---------------------------------------------------------------------------

fn read_bool_attr(path: &Path) -> Result<bool, NmstateError> {
    let raw = fs::read_to_string(path).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!("Failed to read {}: {e}", path.display()),
        )
    })?;
    match raw.trim() {
        "0" => Ok(false),
        "1" => Ok(true),
        other => Err(NmstateError::new(
            ErrorKind::Bug,
            format!(
                "Unexpected value '{}' from {}; expected 0 or 1",
                other,
                path.display()
            ),
        )),
    }
}

/// Like read_bool_attr but returns None when the kernel reports "n/a".
/// bridge_invisible is HiperSockets-only; OSA adapters return "n/a".
fn read_bool_attr_optional(path: &Path) -> Result<Option<bool>, NmstateError> {
    let raw = fs::read_to_string(path).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!("Failed to read {}: {e}", path.display()),
        )
    })?;
    match raw.trim() {
        "0" => Ok(Some(false)),
        "1" => Ok(Some(true)),
        "n/a" => Ok(None),
        other => Err(NmstateError::new(
            ErrorKind::Bug,
            format!(
                "Unexpected value '{}' from {}; expected 0, 1, or n/a",
                other,
                path.display()
            ),
        )),
    }
}

fn read_u32_attr(path: &Path) -> Result<u32, NmstateError> {
    let raw = fs::read_to_string(path).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!("Failed to read {}: {e}", path.display()),
        )
    })?;
    raw.trim().parse::<u32>().map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!("Failed to parse u32 from {}: {e}", path.display()),
        )
    })
}

fn write_bool_attr(path: &Path, value: bool) -> Result<(), NmstateError> {
    let s = if value { "1" } else { "0" };
    fs::write(path, s).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!("Failed to write '{s}' to {}: {e}", path.display()),
        )
    })
}

fn write_u32_attr(path: &Path, value: u32) -> Result<(), NmstateError> {
    fs::write(path, value.to_string()).map_err(|e| {
        NmstateError::new(
            ErrorKind::Bug,
            format!("Failed to write '{value}' to {}: {e}", path.display()),
        )
    })
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Read all vnicc attributes for `iface_name` and return a populated
/// [`VniccConfig`].  Missing attributes are silently ignored (older kernels
/// may not expose every attribute).
pub(crate) fn query_vnicc(
    iface_name: &str,
) -> Result<Option<VniccConfig>, NmstateError> {
    require_s390x()?;

    let dir = match vnicc_dir_for_iface(iface_name) {
        Ok(d) => d,
        // Interface is not a qeth device — return None so callers can skip.
        Err(e) if e.kind() == ErrorKind::InvalidArgument => return Ok(None),
        Err(e) => return Err(e),
    };

    let mut cfg = VniccConfig::default();

    macro_rules! read_bool {
        ($field:ident, $attr:expr) => {
            let p = attr_path(&dir, $attr);
            if p.exists() {
                cfg.$field = Some(read_bool_attr(&p)?);
            }
        };
    }

    read_bool!(flooding, ATTR_FLOODING);
    read_bool!(mcast_flooding, ATTR_MCAST_FLOODING);
    read_bool!(rx_bcast, ATTR_RX_BCAST);
    read_bool!(learning, ATTR_LEARNING);
    read_bool!(takeover_learning, ATTR_TAKEOVER_LEARNING);
    read_bool!(takeover_setvmac, ATTR_TAKEOVER_SETVMAC);
    // bridge_invisible is HiperSockets-only; OSA returns 'n/a'
    let bi_path = attr_path(&dir, ATTR_BRIDGE_INVISIBLE);
    if bi_path.exists() {
        cfg.bridge_invisible = read_bool_attr_optional(&bi_path)?;
    }

    let timeout_path = attr_path(&dir, ATTR_LEARNING_TIMEOUT);
    if timeout_path.exists() {
        cfg.learning_timeout = Some(read_u32_attr(&timeout_path)?);
    }

    Ok(Some(cfg))
}

/// Apply the desired [`VniccConfig`] to `iface_name`.
///
/// Write order matters on real hardware:
///   1. `learning_timeout` before `learning` (kernel requirement).
///   2. All other attributes in any order.
///
/// `rx_bcast` on OSA is read-only — we emit a warning and skip.
pub(crate) fn apply_vnicc(
    iface_name: &str,
    desired: &VniccConfig,
) -> Result<(), NmstateError> {
    require_s390x()?;

    if desired.is_empty() {
        return Ok(());
    }

    desired.validate()?;

    let dir = vnicc_dir_for_iface(iface_name)?;

    // --- learning_timeout MUST be set before learning ---
    if let Some(t) = desired.learning_timeout {
        let p = attr_path(&dir, ATTR_LEARNING_TIMEOUT);
        if p.exists() {
            write_u32_attr(&p, t)?;
            log::debug!("qeth vnicc: set {iface_name} learning-timeout={t}");
        } else {
            log::warn!(
                "qeth vnicc: kernel does not expose learning_timeout for \
                 {iface_name}, skipping"
            );
        }
    }

    macro_rules! apply_bool {
        ($field:ident, $attr:expr) => {
            if let Some(v) = desired.$field {
                let p = attr_path(&dir, $attr);
                if p.exists() {
                    // Check whether the file is writable (rx_bcast on OSA is
                    // read-only; the kernel will return EPERM on write).
                    match write_bool_attr(&p, v) {
                        Ok(()) => log::debug!(
                            "qeth vnicc: set {iface_name} {}={v}",
                            $attr
                        ),
                        Err(e) => {
                            // rx_bcast on OSA returns EPERM; treat as warning.
                            if $attr == ATTR_RX_BCAST {
                                log::warn!(
                                    "qeth vnicc: {iface_name} rx_bcast is \
                                     read-only on OSA adapters, skipping: {e}"
                                );
                            } else {
                                return Err(e);
                            }
                        }
                    }
                } else {
                    log::warn!(
                        "qeth vnicc: kernel does not expose {} for \
                         {iface_name}, skipping",
                        $attr
                    );
                }
            }
        };
    }

    apply_bool!(flooding, ATTR_FLOODING);
    apply_bool!(mcast_flooding, ATTR_MCAST_FLOODING);
    apply_bool!(rx_bcast, ATTR_RX_BCAST); // will warn-and-skip on OSA
    apply_bool!(learning, ATTR_LEARNING); // after timeout
    apply_bool!(takeover_learning, ATTR_TAKEOVER_LEARNING);
    apply_bool!(takeover_setvmac, ATTR_TAKEOVER_SETVMAC);
    apply_bool!(bridge_invisible, ATTR_BRIDGE_INVISIBLE);

    Ok(())
}

/// Verify the post-apply state matches `desired`.
///
/// Called by nmstate's verification pass.  Only fields that were present in
/// `desired` are re-read and compared.
pub(crate) fn verify_vnicc(
    iface_name: &str,
    desired: &VniccConfig,
) -> Result<(), NmstateError> {
    require_s390x()?;

    if desired.is_empty() {
        return Ok(());
    }

    let current = query_vnicc(iface_name)?.unwrap_or_default();

    macro_rules! verify_bool {
        ($field:ident, $label:expr) => {
            if let Some(want) = desired.$field {
                let got = current.$field.unwrap_or(false);
                if got != want {
                    return Err(NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "qeth vnicc {iface_name} {}: desired={want} \
                             current={got}",
                            $label
                        ),
                    ));
                }
            }
        };
    }

    verify_bool!(flooding, "flooding");
    verify_bool!(mcast_flooding, "mcast-flooding");
    // rx_bcast is read-only on OSA; skip verification if we could not set it.
    verify_bool!(learning, "learning");
    verify_bool!(takeover_learning, "takeover-learning");
    verify_bool!(takeover_setvmac, "takeover-setvmac");
    verify_bool!(bridge_invisible, "bridge-invisible");

    if let Some(want) = desired.learning_timeout {
        let got = current.learning_timeout.unwrap_or(600);
        if got != want {
            return Err(NmstateError::new(
                ErrorKind::VerificationError,
                format!(
                    "qeth vnicc {iface_name} learning-timeout: \
                     desired={want} current={got}"
                ),
            ));
        }
    }

    Ok(())
}
