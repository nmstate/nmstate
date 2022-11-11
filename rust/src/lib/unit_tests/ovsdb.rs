use crate::OvsDbGlobalConfig;

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
    let mut desired: OvsDbGlobalConfig = serde_yaml::from_str(
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

    let mut expect: OvsDbGlobalConfig = serde_yaml::from_str(
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

    desired.merge(&current);
    desired.prop_list = Vec::new();
    expect.prop_list = Vec::new();
    assert_eq!(desired, expect);
}

#[test]
fn test_ovsdb_merge_delete_all() {
    let mut desired: OvsDbGlobalConfig = serde_yaml::from_str("{}").unwrap();
    let current = get_current_ovsdb_config();

    let mut expect: OvsDbGlobalConfig = serde_yaml::from_str(
        r#"---
external_ids: {}
other_config: {}
"#,
    )
    .unwrap();

    desired.merge(&current);
    desired.prop_list = Vec::new();
    expect.prop_list = Vec::new();
    assert_eq!(desired, expect);
}

#[test]
fn test_ovsdb_merge_delete_all_external_ids() {
    let mut desired: OvsDbGlobalConfig = serde_yaml::from_str(
        r#"---
external_ids: {}
"#,
    )
    .unwrap();
    let current = get_current_ovsdb_config();

    let mut expect: OvsDbGlobalConfig = serde_yaml::from_str(
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

    desired.merge(&current);
    desired.prop_list = Vec::new();
    expect.prop_list = Vec::new();

    assert_eq!(desired, expect);
}

#[test]
fn test_ovsdb_merge_delete_all_other_config() {
    let mut desired: OvsDbGlobalConfig = serde_yaml::from_str(
        r#"---
other_config: {}
"#,
    )
    .unwrap();
    let current = get_current_ovsdb_config();

    let mut expect: OvsDbGlobalConfig = serde_yaml::from_str(
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

    desired.merge(&current);
    desired.prop_list = Vec::new();
    expect.prop_list = Vec::new();
    assert_eq!(desired, expect);
}
