// SPDX-License-Identifier: Apache-2.0

use crate::{
    DispatchGlobalConfig, ErrorKind, MergedDispatchGlobalConfig,
    MergedInterfaces, MergedNetworkState, NetworkState,
};

#[test]
fn test_duplicate_dispatch_ifaces_types() {
    let desired: DispatchGlobalConfig = serde_yaml::from_str(
        r#"---
        interfaces:
        - type: vxcan
          activation: /opt/abc/a.sh
        - type: vxcan
          activation: /opt/abc/b.sh"#,
    )
    .unwrap();
    let current: DispatchGlobalConfig = serde_yaml::from_str(
        r#"---
        interfaces:
        - type: vxcan
          activation: /opt/abc/c.sh"#,
    )
    .unwrap();

    let result = MergedDispatchGlobalConfig::new(
        &desired,
        &current,
        &mut MergedInterfaces::default(),
    );

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_unknown_dispatch_iface_type() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        dispatch:
          interfaces:
          - type: vxcan
            activation: /opt/abc/b.sh
        interfaces:
          - name: gp1
            type: dispatch
            dispatch:
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
fn test_dispatch_iface_type_is_removing_but_refer_to() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        dispatch:
          interfaces:
          - type: vxcan
            state: absent"#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r#"---
        dispatch:
          interfaces:
          - type: vxcan
            activation: "/opt/vxcan/a.sh"
        interfaces:
          - name: vxcan1
            type: dispatch
            dispatch:
              type: vxcan"#,
    )
    .unwrap();

    let result = MergedNetworkState::new(desired, current, false, false);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_dispatch_iface_type_is_purging_but_refer_to() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        dispatch:
          interfaces: []"#,
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r#"---
        dispatch:
          interfaces:
          - type: vxcan
            activation: "/opt/vxcan/a.sh"
        interfaces:
          - name: vxcan1
            type: dispatch
            dispatch:
              type: vxcan"#,
    )
    .unwrap();

    let result = MergedNetworkState::new(desired, current, false, false);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_dispatch_iface_has_not_allowed_variable() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        dispatch:
          interfaces:
          - type: vxcan
            activation: "/tmp/a.sh"
            allowed-variable-names:
              - "foo"
        interfaces:
          - name: vxcan1
            type: dispatch
            dispatch:
              type: vxcan
              variables:
                foo: abc
                bar: def"#,
    )
    .unwrap();
    let result =
        MergedNetworkState::new(desired, NetworkState::default(), false, false);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_normal_iface_cannot_hold_dispatch_type() {
    let desired: NetworkState = serde_yaml::from_str(
        r#"---
        dispatch:
          interfaces:
          - type: vxcan
            activation: "/tmp/a.sh"
            allowed-variable-names:
              - "foo"
        interfaces:
          - name: dummy1
            type: dummy
            dispatch:
              type: vxcan
              variables:
                foo: abc
                bar: def"#,
    )
    .unwrap();
    let result =
        MergedNetworkState::new(desired, NetworkState::default(), false, false);

    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}
