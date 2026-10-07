// SPDX-License-Identifier: Apache-2.0
//
// qeth_vnicc.rs — VNIC Characteristics (vnicc) support for IBM Z / LinuxONE
// s390x qeth devices (OSA Express and HiperSockets).
//
// IBM documentation:
//   https://www.ibm.com/docs/en/linux-on-systems?topic=bridge-packet-handling
//
// Sysfs knobs live at:
//   /sys/bus/ccwgroup/devices/<device_bus_id>/vnicc/<attribute>
//
// This module is compiled and exposed in the public API on *all* platforms so
// that YAML/JSON deserialization never fails when a manifest authored on an
// s390x node is validated elsewhere.  The *apply* path (writing sysfs) is
// guarded by a runtime architecture check and returns a clear error on
// non-s390x hosts.

use serde::{Deserialize, Serialize};

/// VNIC characteristics for a qeth interface on IBM Z (s390x).
///
/// Example YAML fragment embedded in an `EthernetInterface`:
/// ```yaml
/// interfaces:
///   - name: eth0
///     type: ethernet
///     state: up
///     ethernet:
///       qeth:
///         vnicc:
///           flooding: true
///           mcast-flooding: true
///           learning: true
///           learning-timeout: 600
/// ```
///
/// All fields are `Option<T>` so that a partial desired state merges cleanly
/// with the current state without accidentally resetting un-mentioned knobs.
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct QethConfig {
    /// VNIC characteristics sub-section.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vnicc: Option<VniccConfig>,
}

/// The individual vnicc sysfs knobs exposed as a typed struct.
///
/// All boolean attributes map directly to `0`/`1` in sysfs.
/// `learning_timeout` is written as a decimal integer (seconds).
///
/// Attributes that may be read-only on some devices (e.g. `rx_bcast` on OSA)
/// are exposed for query; when present in the desired state, nmstate will
/// attempt to apply them and will warn-and-skip if the kernel rejects
/// the write.
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
#[non_exhaustive]
pub struct VniccConfig {
    /// Accept packets to unknown destination MAC addresses.
    ///
    /// Sysfs: `vnicc/flooding`  
    /// Default: `false` (disabled).  
    /// Max devices with flooding enabled: 64 (OSA), 16 (HiperSockets).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub flooding: Option<bool>,

    /// Accept multicast packets (required for ARP in bridge setups).
    ///
    /// Sysfs: `vnicc/mcast_flooding`  
    /// Default: `false` (disabled).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mcast_flooding: Option<bool>,

    /// Accept broadcast packets.
    ///
    /// Sysfs: `vnicc/rx_bcast`  
    /// Default: `true`.  
    /// **Read-only on OSA.** nmstate attempts the write and warn-and-skips
    /// if the kernel rejects it (EPERM); the value is best-effort and is
    /// not checked during verification.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_bcast: Option<bool>,

    /// Build a MAC address table from outgoing traffic and receive return
    /// packets for known MACs.  Required for bridge-like behaviour of shared
    /// OSA adapters hosting VM guests with different MAC addresses.
    ///
    /// Sysfs: `vnicc/learning`  
    /// Default: `false` (disabled).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub learning: Option<bool>,

    /// Seconds before a learned MAC address expires (60–86400).
    ///
    /// Sysfs: `vnicc/learning_timeout`  
    /// Default: `600`.  
    /// **Must be set before enabling `learning`.**
    #[serde(skip_serializing_if = "Option::is_none")]
    pub learning_timeout: Option<u32>,

    /// Allow this device's MAC to be taken over by a learning device on the
    /// same channel.
    ///
    /// Sysfs: `vnicc/takeover_learning`  
    /// Default: `false`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub takeover_learning: Option<bool>,

    /// Allow this device's MAC to be configured on a different device without
    /// notification (facilitates live migration / recovery).
    ///
    /// Sysfs: `vnicc/takeover_setvmac`  
    /// Default: `false`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub takeover_setvmac: Option<bool>,

    /// When enabled, suppress traffic between this device and any device
    /// configured as an active z/VM HiperSockets Bridge port.
    ///
    /// Sysfs: `vnicc/bridge_invisible`  
    /// Default: `false`.  
    /// **HiperSockets only.**
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bridge_invisible: Option<bool>,
}

impl VniccConfig {
    /// Returns `true` when every field is `None` (nothing to apply/verify).
    pub fn is_empty(&self) -> bool {
        self.flooding.is_none()
            && self.mcast_flooding.is_none()
            && self.rx_bcast.is_none()
            && self.learning.is_none()
            && self.learning_timeout.is_none()
            && self.takeover_learning.is_none()
            && self.takeover_setvmac.is_none()
            && self.bridge_invisible.is_none()
    }

    /// Validate the `learning_timeout` range (60–86400 seconds).
    pub fn validate(&self) -> Result<(), crate::NmstateError> {
        if let Some(t) = self.learning_timeout
            && !(60..=86400).contains(&t)
        {
            return Err(crate::NmstateError::new(
                crate::ErrorKind::InvalidArgument,
                format!(
                    "qeth vnicc learning-timeout {t} is out of range \
                     60–86400 seconds"
                ),
            ));
        }
        Ok(())
    }

    /// Merge a desired `VniccConfig` on top of `self` (current state),
    /// following the standard nmstate partial-apply semantics: `None` fields
    /// in `desired` are left unchanged.
    pub fn merge_desired(&mut self, desired: &VniccConfig) {
        if desired.flooding.is_some() {
            self.flooding = desired.flooding;
        }
        if desired.mcast_flooding.is_some() {
            self.mcast_flooding = desired.mcast_flooding;
        }
        if desired.rx_bcast.is_some() {
            self.rx_bcast = desired.rx_bcast;
        }
        if desired.learning.is_some() {
            self.learning = desired.learning;
        }
        if desired.learning_timeout.is_some() {
            self.learning_timeout = desired.learning_timeout;
        }
        if desired.takeover_learning.is_some() {
            self.takeover_learning = desired.takeover_learning;
        }
        if desired.takeover_setvmac.is_some() {
            self.takeover_setvmac = desired.takeover_setvmac;
        }
        if desired.bridge_invisible.is_some() {
            self.bridge_invisible = desired.bridge_invisible;
        }
    }
}
