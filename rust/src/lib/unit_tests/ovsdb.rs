// SPDX-License-Identifier: Apache-2.0

use crate::{MergedOvsDbGlobalConfig, NetworkState, OvsDbGlobalConfig};

#[test]
fn test_ovsdb_verify_null_current() {
    let desired: OvsDbGlobalConfig = serde_yaml::from_str("{}").unwrap();
    let pre_apply_current = desired.clone();
    let current = desired.clone();

    let merged_ovsdb =
        MergedOvsDbGlobalConfig::new(Some(desired), pre_apply_current).unwrap();

    merged_ovsdb.verify(current).unwrap();
}

#[test]
fn test_ovsdb_purge_by_empty_section() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        ovs-db: {}
        ",
    )
    .unwrap();

    assert!(desired.ovsdb.unwrap().is_purge());
}

#[test]
fn test_ovsdb_purge_by_empty_hash() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        ovs-db:
          external_ids: {}
          other_config: {}
        ",
    )
    .unwrap();

    assert!(desired.ovsdb.unwrap().is_purge());
}
