use crate::ovn::{
    ovn_bridge_mappings_to_string, MergedOvnConfiguration, OvnBridgeMapping,
    OvnBridgeMappingState,
};
use crate::query_apply::ovn::string_to_ovn_bridge_mappings;
use crate::ErrorKind::InvalidArgument;
use crate::{NmstateError, OvnConfiguration};

#[test]
fn test_ovsdb_merge_with_mappings() {
    let desired: OvnConfiguration = serde_yaml::from_str(
        r#"---
bridge-mappings:
- localnet: net1
  state: present
  bridge: br1
"#,
    )
    .unwrap();

    let current: OvnConfiguration = serde_yaml::from_str(
        r#"---
bridge-mappings: []
        "#,
    )
    .unwrap();

    let merged_ovsdb = MergedOvnConfiguration::new(desired, current).unwrap();

    let expect: OvnConfiguration = serde_yaml::from_str(
        r#"---
bridge-mappings:
- localnet: net1
  state: present
  bridge: br1
"#,
    )
    .unwrap();

    assert_eq!(
        merged_ovsdb.bridge_mappings,
        expect.bridge_mappings.unwrap()
    );
}

#[test]
fn test_ovsdb_merge_delete_existing_mappings() {
    let desired: OvnConfiguration = serde_yaml::from_str(
        r#"---
bridge-mappings:
- localnet: net1
  state: absent
  bridge: br1
"#,
    )
    .unwrap();

    let current: OvnConfiguration = serde_yaml::from_str(
        r#"---
bridge-mappings:
- localnet: net1
  state: present
  bridge: br1
"#,
    )
    .unwrap();

    let merged_ovsdb = MergedOvnConfiguration::new(desired, current).unwrap();

    let expect: OvnConfiguration = serde_yaml::from_str(
        r#"---
bridge-mappings: []
"#,
    )
    .unwrap();

    assert_eq!(
        merged_ovsdb.bridge_mappings,
        expect.bridge_mappings.unwrap_or_default()
    );
}

#[test]
fn test_ovn_duplicate_localnet_keys_are_forbidden_on_desired_state() {
    let desired: OvnConfiguration = serde_yaml::from_str(
        r#"---
bridge-mappings:
- localnet: net1
  bridge: br1
- localnet: net1
  state: absent
"#,
    )
    .unwrap();

    let current: OvnConfiguration = serde_yaml::from_str(
        r#"---
bridge-mappings:
- localnet: net1
  state: present
  bridge: br1
"#,
    )
    .unwrap();

    assert_eq!(
        MergedOvnConfiguration::new(desired, current),
        Err(NmstateError::new(
            InvalidArgument,
            "Duplicated `localnet` keys in the provided ovn.bridge-mappings"
                .to_string()
        ))
    )
}

#[test]
fn test_ovsdb_empty_string_to_ovn_bridge_mappings() {
    let input_string = "";
    assert_eq!(
        string_to_ovn_bridge_mappings(input_string.to_string()),
        Ok(Vec::new())
    )
}

#[test]
fn test_ovsdb_string_without_localnet_to_ovn_bridge_mappings() {
    let input_string = ":br1";
    assert_eq!(
        string_to_ovn_bridge_mappings(input_string.to_string()),
        Err(NmstateError::new(
            InvalidArgument,
            "expected `<localnet>:<bridge>`, got: :br1".to_string()
        ))
    )
}

#[test]
fn test_ovsdb_string_without_bridge_to_ovn_bridge_mappings() {
    let input_string = "net1:";
    assert_eq!(
        string_to_ovn_bridge_mappings(input_string.to_string()),
        Err(NmstateError::new(
            InvalidArgument,
            "expected `<localnet>:<bridge>`, got: net1:".to_string()
        ))
    )
}

#[test]
fn test_ovsdb_string_to_ovn_bridge_mappings() {
    let input_string = "net1:br1";
    assert_eq!(
        string_to_ovn_bridge_mappings(input_string.to_string()),
        Ok(vec!(OvnBridgeMapping {
            localnet: "net1".to_string(),
            bridge: Some("br1".to_string()),
            state: Some(OvnBridgeMappingState::Present)
        }))
    )
}

#[test]
fn test_ovsdb_string_to_multiple_ovn_bridge_mappings() {
    let input_string = "net1:br1,net32:br1";
    assert_eq!(
        string_to_ovn_bridge_mappings(input_string.to_string()),
        Ok(vec!(
            OvnBridgeMapping {
                localnet: "net1".to_string(),
                bridge: Some("br1".to_string()),
                state: Some(OvnBridgeMappingState::Present)
            },
            OvnBridgeMapping {
                localnet: "net32".to_string(),
                bridge: Some("br1".to_string()),
                state: Some(OvnBridgeMappingState::Present)
            },
        ))
    )
}

#[test]
fn test_empty_mappings() {
    assert_eq!(ovn_bridge_mappings_to_string(Vec::new()), "")
}

#[test]
fn test_mappings_missing_bridge() {
    let mappings: Vec<OvnBridgeMapping> = vec![OvnBridgeMapping {
        localnet: "localnet1".to_string(),
        state: Default::default(),
        bridge: None,
    }];
    assert_eq!(ovn_bridge_mappings_to_string(mappings), "")
}

#[test]
fn test_mappings_with_required_data() {
    let mappings: Vec<OvnBridgeMapping> = vec![OvnBridgeMapping {
        localnet: "localnet1".to_string(),
        state: Default::default(),
        bridge: Some("br1".to_string()),
    }];
    assert_eq!(ovn_bridge_mappings_to_string(mappings), "localnet1:br1")
}

#[test]
fn test_multiple_mappings_with_required_data() {
    let mappings: Vec<OvnBridgeMapping> = vec![
        OvnBridgeMapping {
            localnet: "localnet1".to_string(),
            state: Default::default(),
            bridge: Some("br1".to_string()),
        },
        OvnBridgeMapping {
            localnet: "localnet2".to_string(),
            state: Default::default(),
            bridge: Some("br2".to_string()),
        },
    ];
    assert_eq!(
        ovn_bridge_mappings_to_string(mappings),
        "localnet1:br1,localnet2:br2"
    )
}
