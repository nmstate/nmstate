// SPDX-License-Identifier: Apache-2.0
//
// test_qeth_vnicc.rs
// tests/integration/test_qeth_vnicc.rs
//
// Integration tests for the qeth vnicc feature.
//
// These tests are skipped automatically on non-s390x hosts.
// On a real IBM Z node they require:
//   - A qeth OSA or HiperSockets device exposed as an ethernet interface.
//   - The kernel module `qeth` loaded with vnicc sysfs support (kernel ≥ 5.2).
//   - Sufficient privileges to write sysfs attributes (root or CAP_NET_ADMIN).
//
// Run on s390x:
//   cargo test --test test_qeth_vnicc -- --nocapture
//
// The environment variable NMSTATE_TEST_IFACE must be set to a qeth interface
// name (e.g. `eth0`) for the tests to execute.

use nmstate::{NetworkState, VniccConfig};

fn test_iface() -> Option<String> {
    std::env::var("NMSTATE_TEST_IFACE").ok()
}

fn is_s390x() -> bool {
    cfg!(target_arch = "s390x")
        || std::fs::read_to_string("/proc/version")
            .unwrap_or_default()
            .contains("s390")
}

// ---------------------------------------------------------------------------
// Helper: apply a desired state and return the current state afterwards
// ---------------------------------------------------------------------------

fn apply_and_read(yaml: &str) -> NetworkState {
    let mut state: NetworkState = serde_yaml::from_str(yaml).expect("yaml parse");
    state.set_kernel_only(true);
    state.apply().expect("nmstate apply");

    let mut cur = NetworkState::new();
    cur.retrieve().expect("retrieve");
    cur
}

// ---------------------------------------------------------------------------
// Test: enable flooding + mcast_flooding + learning for KubeVirt use-case
// ---------------------------------------------------------------------------

#[test]
fn test_vnicc_bridge_mode_for_kubevirt() {
    if !is_s390x() {
        eprintln!("Skipping: not s390x");
        return;
    }
    let iface = match test_iface() {
        Some(i) => i,
        None => {
            eprintln!("Skipping: NMSTATE_TEST_IFACE not set");
            return;
        }
    };

    let yaml = format!(
        r#"---
interfaces:
  - name: {iface}
    type: ethernet
    state: up
    ethernet:
      qeth:
        vnicc:
          flooding: true
          mcast-flooding: true
          learning: true
          learning-timeout: 600
"#
    );

    let after = apply_and_read(&yaml);
    let eth_iface = after
        .interfaces
        .get_iface(&iface, nmstate::InterfaceType::Ethernet)
        .expect("interface not found");

    if let nmstate::Interface::Ethernet(eth) = eth_iface {
        let vnicc = eth
            .ethernet
            .as_ref()
            .and_then(|e| e.qeth.as_ref())
            .expect("qeth missing")
            .vnicc
            .as_ref()
            .expect("vnicc missing");

        assert_eq!(vnicc.flooding, Some(true), "flooding");
        assert_eq!(vnicc.mcast_flooding, Some(true), "mcast_flooding");
        assert_eq!(vnicc.learning, Some(true), "learning");
        assert_eq!(vnicc.learning_timeout, Some(600), "learning_timeout");
    } else {
        panic!("Expected EthernetInterface");
    }
}

// ---------------------------------------------------------------------------
// Test: partial desired state — only enable learning, leave others unchanged
// ---------------------------------------------------------------------------

#[test]
fn test_vnicc_partial_desired() {
    if !is_s390x() {
        eprintln!("Skipping: not s390x");
        return;
    }
    let iface = match test_iface() {
        Some(i) => i,
        None => {
            eprintln!("Skipping: NMSTATE_TEST_IFACE not set");
            return;
        }
    };

    // First, set a known baseline.
    let baseline_yaml = format!(
        r#"---
interfaces:
  - name: {iface}
    type: ethernet
    state: up
    ethernet:
      qeth:
        vnicc:
          flooding: false
          mcast-flooding: false
          learning: false
"#
    );
    let mut baseline: NetworkState = serde_yaml::from_str(&baseline_yaml).unwrap();
    baseline.set_kernel_only(true);
    baseline.apply().unwrap();

    // Apply partial: only enable learning.
    let partial_yaml = format!(
        r#"---
interfaces:
  - name: {iface}
    type: ethernet
    state: up
    ethernet:
      qeth:
        vnicc:
          learning: true
"#
    );
    let after = apply_and_read(&partial_yaml);
    let eth_iface = after
        .interfaces
        .get_iface(&iface, nmstate::InterfaceType::Ethernet)
        .unwrap();

    if let nmstate::Interface::Ethernet(eth) = eth_iface {
        let vnicc = eth
            .ethernet
            .as_ref()
            .unwrap()
            .qeth
            .as_ref()
            .unwrap()
            .vnicc
            .as_ref()
            .unwrap();
        // learning should be on
        assert_eq!(vnicc.learning, Some(true));
        // flooding should still be off (we did not touch it)
        assert_eq!(vnicc.flooding, Some(false));
    }
}

// ---------------------------------------------------------------------------
// Test: learning_timeout out-of-range is rejected before apply
// ---------------------------------------------------------------------------

#[test]
fn test_vnicc_invalid_timeout_rejected() {
    let yaml = r#"---
interfaces:
  - name: eth0
    type: ethernet
    state: up
    ethernet:
      qeth:
        vnicc:
          learning-timeout: 30
"#;
    let state: NetworkState = serde_yaml::from_str(yaml).unwrap();
    // Validation is triggered during apply(); on non-s390x hosts the
    // architecture guard fires first. Either way apply() must return Err.
    // On s390x: learning_timeout=30 fails VniccConfig::validate() before apply.
    // On non-s390x: require_s390x() returns NotImplementedError.
    // Either way apply() must return Err.
    assert!(state.apply().is_err());
}

// ---------------------------------------------------------------------------
// Test: YAML round-trip for VniccConfig
// ---------------------------------------------------------------------------

#[test]
fn test_vnicc_yaml_round_trip() {
    let mut cfg = VniccConfig::default();
    cfg.flooding = Some(true);
    cfg.mcast_flooding = Some(true);
    cfg.learning = Some(true);
    cfg.learning_timeout = Some(600);
    cfg.takeover_learning = Some(false);
    cfg.takeover_setvmac = Some(false);
    cfg.bridge_invisible = Some(false);

    let yaml = serde_yaml::to_string(&cfg).unwrap();
    let back: VniccConfig = serde_yaml::from_str(&yaml).unwrap();
    assert_eq!(cfg, back);
}

// ---------------------------------------------------------------------------
// Test: unknown fields are rejected (deny_unknown_fields)
// ---------------------------------------------------------------------------

#[test]
fn test_vnicc_unknown_field_rejected() {
    let bad_yaml = r#"
flooding: true
unknown-knob: true
"#;
    let result: Result<VniccConfig, _> = serde_yaml::from_str(bad_yaml);
    assert!(result.is_err(), "unknown field should be rejected");
}
