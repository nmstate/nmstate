// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, Interfaces, MergedInterfaces, MergedNetworkState,
    MergedOvnConfiguration, NetworkState, OvnBridgeMapping,
    OvnBridgeMappingState, OvnConfiguration,
};

fn gen_br1_merged_ifaces() -> MergedInterfaces {
    let desired_ifaces: Interfaces = serde_yaml::from_str(
        r"---
         - name: br1
           type: ovs-bridge
           state: up
           bridge:
             options:
               stp: true
             port:
             - name: eth1
        ",
    )
    .unwrap();
    let current_ifaces: Interfaces = serde_yaml::from_str(
        r"---
         - name: eth1
           type: ethernet
           state: up
        ",
    )
    .unwrap();
    MergedInterfaces::new(
        desired_ifaces,
        current_ifaces,
        Default::default(),
        false,
    )
    .unwrap()
}

#[test]
fn test_ovsdb_merge_with_mappings() {
    let desired: OvnConfiguration = serde_yaml::from_str(
        r"---
        bridge-mappings:
        - localnet: net1
          bridge: br1",
    )
    .unwrap();

    let current: OvnConfiguration = serde_yaml::from_str(
        r"---
bridge-mappings: []
        ",
    )
    .unwrap();

    let merged_ovsdb =
        MergedOvnConfiguration::new(desired, current, &gen_br1_merged_ifaces())
            .unwrap();

    assert_eq!(
        merged_ovsdb.to_ovsdb_external_id_value().unwrap(),
        "net1:br1"
    );
}

#[test]
fn test_ovsdb_merge_delete_existing_mappings() {
    let desired: OvnConfiguration = serde_yaml::from_str(
        r"---
        bridge-mappings:
        - localnet: net1
          state: absent
          bridge: br1",
    )
    .unwrap();

    let current: OvnConfiguration = serde_yaml::from_str(
        r"---
        bridge-mappings:
        - localnet: net1
          bridge: br1",
    )
    .unwrap();

    let merged_ovsdb =
        MergedOvnConfiguration::new(desired, current, &gen_br1_merged_ifaces())
            .unwrap();
    assert_eq!(merged_ovsdb.to_ovsdb_external_id_value(), None);
}

#[test]
fn test_ovn_duplicate_localnet_keys_are_forbidden_on_desired_state() {
    let desired: OvnConfiguration = serde_yaml::from_str(
        r"---
        bridge-mappings:
        - localnet: net1
          bridge: br1
        - localnet: net1
          state: absent",
    )
    .unwrap();

    let current: OvnConfiguration = serde_yaml::from_str(
        r"---
        bridge-mappings:
        - localnet: net1
          bridge: br1",
    )
    .unwrap();

    let result =
        MergedOvnConfiguration::new(desired, current, &gen_br1_merged_ifaces());

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovsdb_empty_string_to_ovn_bridge_mappings() {
    let input_string = "";
    let result = OvnBridgeMapping::try_from(input_string);
    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovsdb_string_without_localnet_to_ovn_bridge_mappings() {
    let input_string = ":br1";
    let result = OvnConfiguration::try_from(input_string);

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovsdb_string_without_bridge_to_ovn_bridge_mappings() {
    let input_string = "net1:";
    let result = OvnConfiguration::try_from(input_string);

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovsdb_string_to_ovn_bridge_mappings() {
    let input_string = "net1:br1";

    assert_eq!(
        OvnBridgeMapping::try_from(input_string).unwrap(),
        OvnBridgeMapping {
            localnet: "net1".to_string(),
            bridge: Some("br1".to_string()),
            state: None
        }
    )
}

#[test]
fn test_ovsdb_string_to_multiple_ovn_bridge_mappings() {
    let input_string = "net1:br1,net32:br1";
    let conf = OvnConfiguration::try_from(input_string).unwrap();
    assert_eq!(
        conf.bridge_mappings,
        Some(vec!(
            OvnBridgeMapping {
                localnet: "net1".to_string(),
                bridge: Some("br1".to_string()),
                state: None
            },
            OvnBridgeMapping {
                localnet: "net32".to_string(),
                bridge: Some("br1".to_string()),
                state: None
            },
        ))
    )
}

#[test]
fn test_empty_mappings() {
    assert_eq!(
        OvnConfiguration::try_from("").unwrap(),
        OvnConfiguration::default()
    )
}

#[test]
fn test_mappings_missing_bridge() {
    let conf = OvnConfiguration {
        bridge_mappings: Some(vec![OvnBridgeMapping {
            localnet: "localnet1".to_string(),
            state: Default::default(),
            bridge: None,
        }]),
    };
    assert_eq!(conf.to_ovsdb_external_id_value().unwrap(), "")
}

#[test]
fn test_mappings_with_required_data() {
    let conf = OvnConfiguration {
        bridge_mappings: Some(vec![OvnBridgeMapping {
            localnet: "localnet1".to_string(),
            state: Default::default(),
            bridge: Some("br1".to_string()),
        }]),
    };
    assert_eq!(conf.to_ovsdb_external_id_value().unwrap(), "localnet1:br1")
}

#[test]
fn test_multiple_mappings_with_required_data() {
    let conf = OvnConfiguration {
        bridge_mappings: Some(vec![
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
        ]),
    };
    assert_eq!(
        conf.to_ovsdb_external_id_value().unwrap(),
        "localnet1:br1,localnet2:br2"
    )
}

#[test]
fn test_sanitize_mapping_add_without_bridge() {
    let mut mapping = OvnBridgeMapping {
        localnet: "localnet1".to_string(),
        state: Default::default(),
        bridge: None,
    };
    let result = mapping.sanitize();

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_sanitize_correct_mapping_add() {
    let mut mapping = OvnBridgeMapping {
        localnet: "localnet1".to_string(),
        state: Default::default(),
        bridge: Some("bridge".to_string()),
    };
    assert_eq!(mapping.sanitize(), Ok(()))
}

#[test]
fn test_sanitize_correct_mapping_remove() {
    let mut mapping = OvnBridgeMapping {
        localnet: "localnet1".to_string(),
        state: Some(OvnBridgeMappingState::Absent),
        bridge: None,
    };
    assert_eq!(mapping.sanitize(), Ok(()))
}

#[test]
fn test_ovn_map_support_state_present() {
    let mut desired: OvnConfiguration = serde_yaml::from_str(
        r"---
        bridge-mappings:
        - localnet: net1
          state: present
          bridge: br1",
    )
    .unwrap();
    desired.sanitize().unwrap();

    assert_eq!(
        desired.bridge_mappings.unwrap(),
        vec![OvnBridgeMapping {
            localnet: "net1".to_string(),
            state: None,
            bridge: Some("br1".to_string())
        }]
    )
}

#[test]
fn test_ovn_serialize_state_absent() {
    let desired: OvnConfiguration = serde_yaml::from_str(
        r#"---
        bridge-mappings:
        - localnet: blue
          state: absent
        - localnet: red
          state: absent
        - localnet: yellow
          state: absent
        - localnet: green
        "#,
    )
    .unwrap();

    let new: OvnConfiguration =
        serde_yaml::from_str(&serde_yaml::to_string(&desired).unwrap())
            .unwrap();

    assert_eq!(desired, new);
}

#[test]
fn test_ovn_bridge_not_found() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        interfaces:
        - name: br1
          type: ovs-bridge
          state: up
          bridge:
            options:
              stp: true
            port:
            - name: eth1
        ovn:
          bridge-mappings:
          - localnet: vlan-99
            bridge: ovs-not-exist
            state: present"#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
        ",
    )
    .unwrap();

    let result =
        MergedNetworkState::new(desired, current, Default::default(), false);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovn_ref_to_absent_bridge() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        interfaces:
        - name: br1
          type: ovs-bridge
          state: absent
        ovn:
          bridge-mappings:
          - localnet: vlan-99
            bridge: br1
            state: present"#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
        - name: br1
          type: ovs-bridge
          state: up
          bridge:
            options:
              stp: true
            port:
            - name: eth1
        ",
    )
    .unwrap();

    let result =
        MergedNetworkState::new(desired, current, Default::default(), false);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ovn_absent_ref_to_absent_bridge() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        interfaces:
        - name: br1
          type: ovs-bridge
          state: absent
        ovn:
          bridge-mappings:
          - localnet: vlan-99
            bridge: br1
            state: absent"#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
        - name: br1
          type: ovs-bridge
          state: up
          bridge:
            options:
              stp: true
            port:
            - name: eth1
        ",
    )
    .unwrap();

    MergedNetworkState::new(desired, current, Default::default(), false)
        .unwrap();
}
