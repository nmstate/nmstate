// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, MergedNetworkState, NetworkState};

#[test]
fn test_alt_name_conflict_with_other_port() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: port1
            type: ethernet
            identifier: mac-address
            mac-address: 52:54:00:15:17:63
            alt-names:
              - name: port1
              - name: veryveryveryverylonglonglongname
          - name: bond99
            type: bond
            bond:
              mode: 0
              ports:
                - eth1
                - veryveryveryverylonglonglongname",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            mac-address: 52:54:00:15:17:63",
    )
    .unwrap();

    let result =
        MergedNetworkState::new(desired, current, Default::default(), false);

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("eth1"));
        assert!(e.msg().contains("bond99"));
        assert!(e.msg().contains("veryveryveryverylonglonglongname"));
    }
}

#[test]
fn test_two_alt_name_conflict_with_each_other() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: port1
            type: ethernet
            identifier: mac-address
            mac-address: 52:54:00:15:17:63
            alt-names:
              - name: port1
              - name: veryveryveryverylonglonglongname
          - name: bond99
            type: bond
            bond:
              mode: 0
              ports:
                - port1
                - veryveryveryverylonglonglongname",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            mac-address: 52:54:00:15:17:63",
    )
    .unwrap();

    let result =
        MergedNetworkState::new(desired, current, Default::default(), false);

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("eth1"));
        assert!(e.msg().contains("bond99"));
        assert!(e.msg().contains("veryveryveryverylonglonglongname"));
    }
}

#[test]
fn test_alt_name_overbook() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: port1
            type: ethernet
            identifier: mac-address
            mac-address: 52:54:00:15:17:63
            alt-names:
              - name: port1
              - name: veryveryveryverylonglonglongname
          - name: bond99
            type: bond
            bond:
              mode: 0
              ports:
                - port1
          - name: bond98
            type: bond
            bond:
              mode: 0
              ports:
                - veryveryveryverylonglonglongname",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            mac-address: 52:54:00:15:17:63",
    )
    .unwrap();

    let result =
        MergedNetworkState::new(desired, current, Default::default(), false);

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("eth1"));
        assert!(e.msg().contains("bond99"));
        assert!(e.msg().contains("bond98"));
        assert!(e.msg().contains("overbook"));
    }
}
