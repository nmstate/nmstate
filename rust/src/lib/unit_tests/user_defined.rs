// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, MergedNetworkState, MergedUserDefinedData, NetworkState,
    UserDefinedData,
};

#[test]
fn test_duplicate_user_ifaces_types() {
    let desired: UserDefinedData = serde_yaml::from_str(
        r#"---
        interface-types:
        - name: vxcan
          handler-script: /opt/abc/a.sh
        - name: vxcan
          handler-script: /opt/abc/b.sh"#,
    )
    .unwrap();
    let current: UserDefinedData = serde_yaml::from_str(
        r#"---
        interface-types:
        - name: vxcan
          handler-script: /opt/abc/c.sh"#,
    )
    .unwrap();

    let result = MergedUserDefinedData::new(&desired, &current);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_unknown_user_defined_iface_type() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        user-defined:
          interface-types:
          - name: vxcan
            handler-script: /opt/abc/b.sh
        interfaces:
          - name: gp1
            type: gp"#,
    )
    .unwrap();
    let current = NetworkState::default();

    let result = MergedNetworkState::new(desired, current, false, false);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_user_defined_iface_type_is_removing_but_refer_to() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        user-defined:
          interface-types:
          - name: vxcan
            handler-script: ""
        interfaces:
          - name: vxcan1
            type: vxcan"#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r#"---
        user-defined:
          interface-types:
          - name: vxcan
            handler-script: "/opt/vxcan/a.sh""#,
    )
    .unwrap();

    let result = MergedNetworkState::new(desired, current, false, false);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_user_defined_iface_type_is_purging_but_refer_to() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        user-defined:
          interface-types: []
        interfaces:
          - name: vxcan1
            type: vxcan"#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r#"---
        user-defined:
          interface-types:
          - name: vxcan
            handler-script: "/opt/vxcan/a.sh""#,
    )
    .unwrap();

    let result = MergedNetworkState::new(desired, current, false, false);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_user_defined_iface_type_is_purging_by_empty_list_but_refer_to() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        user-defined:
          interface-types: []
        interfaces:
          - name: vxcan1
            type: vxcan"#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r#"---
        user-defined:
          interface-types:
          - name: vxcan
            handler-script: "/opt/vxcan/a.sh""#,
    )
    .unwrap();

    let result = MergedNetworkState::new(desired, current, false, false);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}
