use crate::state::get_json_value_difference;

#[test]
fn test_verify_stringlized_boolean() {
    let desired: serde_json::Value = serde_yaml::from_str(
        r#"---
backend-specific:
  boolean_false:
    a: "False"
    b: "false"
    c: "no"
    d: "n"
    e: "0"
  boolean_true:
    a: "True"
    b: "true"
    c: "yes"
    d: "y"
    e: "1"
  boolean_uint:
    a: "124567"
  boolean_int:
    a: "-124567"
"#,
    )
    .unwrap();

    let current: serde_json::Value = serde_yaml::from_str(
        r#"---
backend-specific:
  boolean_false:
    a: false
    b: false
    c: false
    d: false
    e: false
  boolean_true:
    a: true
    b: true
    c: true
    d: true
    e: true
  boolean_uint:
    a: 124567
  boolean_int:
    a: -124567
"#,
    )
    .unwrap();
    assert_eq!(
        get_json_value_difference("".to_string(), &desired, &current),
        None
    );
}
