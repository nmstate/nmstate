// SPDX-License-Identifier: Apache-2.0

use crate::NetworkState;

#[test]
fn test_invalid_top_key() {
    let result = serde_yaml::from_str::<NetworkState>(
        r#"---
invalid_key: abc
"#,
    );

    assert!(result.is_err());
}

#[test]
fn test_invalid_top_type() {
    let result = serde_yaml::from_str::<NetworkState>(
        r#"---
- invalid_key: abc
"#,
    );

    assert!(result.is_err());
}
