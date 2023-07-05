// SPDX-License-Identifier: Apache-2.0

use crate::{MergedOvsDbGlobalConfig, OvsDbGlobalConfig};

fn get_current_ovsdb_config() -> OvsDbGlobalConfig {
    serde_yaml::from_str(
        r#"---
external_ids:
  a: A0
  b: B0
  c: C0
  h: H0
other_config:
  d: D0
  e: E0
  f: F0
  g: G0
"#,
    )
    .unwrap()
}

#[test]
fn test_ovsdb_merge_with_override_and_delete() {
    let desired: OvsDbGlobalConfig = serde_yaml::from_str(
        r#"---
external_ids:
  a: A
  b: B
  c: null
other_config:
  d: null
  e: E
  f: F
"#,
    )
    .unwrap();

    let current = get_current_ovsdb_config();

    let merged_ovsdb = MergedOvsDbGlobalConfig::new(desired, current).unwrap();

    let expect: OvsDbGlobalConfig = serde_yaml::from_str(
        r#"---
external_ids:
  a: A
  b: B
  h: H0
other_config:
  e: E
  f: F
  g: G0
"#,
    )
    .unwrap();

    assert_eq!(
        &merged_ovsdb.external_ids,
        expect.external_ids.as_ref().unwrap()
    );
    assert_eq!(
        &merged_ovsdb.other_config,
        expect.other_config.as_ref().unwrap()
    );
}

#[test]
fn test_ovsdb_merge_delete_all() {
    let desired: OvsDbGlobalConfig = serde_yaml::from_str("{}").unwrap();
    let current = get_current_ovsdb_config();

    let expect: OvsDbGlobalConfig = serde_yaml::from_str(
        r#"---
external_ids: {}
other_config: {}
"#,
    )
    .unwrap();

    let merged_ovsdb = MergedOvsDbGlobalConfig::new(desired, current).unwrap();

    assert_eq!(
        &merged_ovsdb.external_ids,
        expect.external_ids.as_ref().unwrap()
    );
    assert_eq!(
        &merged_ovsdb.other_config,
        expect.other_config.as_ref().unwrap()
    );
}

#[test]
fn test_ovsdb_merge_delete_all_external_ids() {
    let desired: OvsDbGlobalConfig = serde_yaml::from_str(
        r#"---
external_ids: {}
"#,
    )
    .unwrap();
    let current = get_current_ovsdb_config();

    let expect: OvsDbGlobalConfig = serde_yaml::from_str(
        r#"---
external_ids: {}
other_config:
  d: D0
  e: E0
  f: F0
  g: G0
"#,
    )
    .unwrap();

    let merged_ovsdb = MergedOvsDbGlobalConfig::new(desired, current).unwrap();

    assert_eq!(
        &merged_ovsdb.external_ids,
        expect.external_ids.as_ref().unwrap()
    );
    assert_eq!(
        &merged_ovsdb.other_config,
        expect.other_config.as_ref().unwrap()
    );
}

#[test]
fn test_ovsdb_merge_delete_all_other_config() {
    let desired: OvsDbGlobalConfig = serde_yaml::from_str(
        r#"---
other_config: {}
"#,
    )
    .unwrap();
    let current = get_current_ovsdb_config();

    let expect: OvsDbGlobalConfig = serde_yaml::from_str(
        r#"---
external_ids:
  a: A0
  b: B0
  c: C0
  h: H0
other_config: {}
"#,
    )
    .unwrap();

    let merged_ovsdb = MergedOvsDbGlobalConfig::new(desired, current).unwrap();

    assert_eq!(
        &merged_ovsdb.external_ids,
        expect.external_ids.as_ref().unwrap()
    );
    assert_eq!(
        &merged_ovsdb.other_config,
        expect.other_config.as_ref().unwrap()
    );
}

#[test]
fn test_ovsdb_verify_null_current() {
    let desired: OvsDbGlobalConfig = serde_yaml::from_str("{}").unwrap();
    let pre_apply_current = desired.clone();
    let current = desired.clone();

    let merged_ovsdb =
        MergedOvsDbGlobalConfig::new(desired, pre_apply_current).unwrap();

    merged_ovsdb.verify(&current).unwrap();
}
