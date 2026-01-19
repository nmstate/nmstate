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

#[test]
fn test_remove_iface_via_alt_name_ref() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: veryveryveryverylonglonglongname
            type: ethernet
            state: absent",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            mac-address: 52:54:00:15:17:63
            alt-names:
              - name: port1
              - name: veryveryveryverylonglonglongname",
    )
    .unwrap();

    let merged_state =
        MergedNetworkState::new(desired, current, Default::default(), false)
            .unwrap();

    let merged_iface =
        merged_state.interfaces.kernel_ifaces.get("eth1").unwrap();
    let for_apply = merged_iface.for_apply.as_ref().unwrap();
    let for_verify = merged_iface.for_verify.as_ref().unwrap();
    let merged = &merged_iface.merged;

    assert!(for_apply.is_absent());
    assert!(for_verify.is_absent());
    assert!(merged.is_absent());
}

#[test]
fn test_change_iface_via_alt_name_ref() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: veryveryveryverylonglonglongname
            type: ethernet
            state: up
            ipv4:
              enabled: true
              dhcp: true",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            mac-address: 52:54:00:15:17:63
            alt-names:
              - name: port1
              - name: veryveryveryverylonglonglongname
            ipv4:
              enabled: false
              ",
    )
    .unwrap();

    let merged_state =
        MergedNetworkState::new(desired, current, Default::default(), false)
            .unwrap();

    let merged_iface =
        merged_state.interfaces.kernel_ifaces.get("eth1").unwrap();
    let for_apply = merged_iface.for_apply.as_ref().unwrap();
    let for_verify = merged_iface.for_verify.as_ref().unwrap();
    let merged = &merged_iface.merged;

    assert_eq!(
        for_apply.base_iface().profile_name.as_deref(),
        Some("veryveryveryverylonglonglongname")
    );
    assert_eq!(
        for_apply.base_iface().ipv4.as_ref().map(|i| i.enabled),
        Some(true)
    );
    assert_eq!(
        for_apply.base_iface().ipv4.as_ref().and_then(|i| i.dhcp),
        Some(true)
    );

    assert_eq!(
        for_verify.base_iface().profile_name.as_deref(),
        Some("veryveryveryverylonglonglongname")
    );
    assert_eq!(
        for_verify.base_iface().ipv4.as_ref().map(|i| i.enabled),
        Some(true)
    );
    assert_eq!(
        for_verify.base_iface().ipv4.as_ref().and_then(|i| i.dhcp),
        Some(true)
    );

    assert_eq!(
        merged.base_iface().profile_name.as_deref(),
        Some("veryveryveryverylonglonglongname")
    );

    assert_eq!(
        merged.base_iface().ipv4.as_ref().map(|i| i.enabled),
        Some(true)
    );
    assert_eq!(
        merged.base_iface().ipv4.as_ref().and_then(|i| i.dhcp),
        Some(true)
    );
}

#[test]
fn test_iface_ref_by_alt_name_but_desired_as_absent() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            state: absent
          - name: veryveryveryverylonglonglongname
            type: ethernet
            state: up
            ipv4:
              enabled: true
              dhcp: true",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            mac-address: 52:54:00:15:17:63
            alt-names:
              - name: port1
              - name: veryveryveryverylonglonglongname
            ipv4:
              enabled: false",
    )
    .unwrap();

    let result =
        MergedNetworkState::new(desired, current, Default::default(), false);

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("eth1"));
        assert!(e.msg().contains("veryveryveryverylonglonglongname"));
        assert!(e.msg().contains("conflict"));
    }
}

#[test]
fn test_iface_ref_by_alt_name_but_conflict_desired() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
          - name: veryveryveryverylonglonglongname
            type: ethernet
            state: up
            ipv4:
              enabled: true
              dhcp: true",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            mac-address: 52:54:00:15:17:63
            alt-names:
              - name: port1
              - name: veryveryveryverylonglonglongname
            ipv4:
              enabled: false",
    )
    .unwrap();

    let result =
        MergedNetworkState::new(desired, current, Default::default(), false);

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("eth1"));
        assert!(e.msg().contains("veryveryveryverylonglonglongname"));
        assert!(e.msg().contains("conflict"));
    }
}

#[test]
fn test_iface_ref_by_alt_name_ok_to_conflict_when_both_absent() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            state: absent
          - name: veryveryveryverylonglonglongname
            type: ethernet
            state: absent",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            mac-address: 52:54:00:15:17:63
            alt-names:
              - name: port1
              - name: veryveryveryverylonglonglongname
            ipv4:
              enabled: false",
    )
    .unwrap();
    let merged_state =
        MergedNetworkState::new(desired, current, Default::default(), false)
            .unwrap();

    let merged_iface =
        merged_state.interfaces.kernel_ifaces.get("eth1").unwrap();
    let for_apply = merged_iface.for_apply.as_ref().unwrap();
    let for_verify = merged_iface.for_verify.as_ref().unwrap();
    let merged = &merged_iface.merged;

    assert!(for_apply.is_absent());
    assert!(for_verify.is_absent());
    assert!(merged.is_absent());
}

#[test]
fn test_do_not_resolve_mac_identifer_iface_to_alt_name() {
    let desired: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: port1
            type: ethernet
            identifier: mac-address
            mac-address: 52:54:00:15:17:64
            state: absent",
    )
    .unwrap();
    let current: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
          - name: eth1
            type: ethernet
            mac-address: 52:54:00:15:17:63
            alt-names:
              - name: port1
              - name: veryveryveryverylonglonglongname
            ipv4:
              enabled: false
          - name: eth2
            type: ethernet
            mac-address: 52:54:00:15:17:64
            ipv4:
              enabled: false",
    )
    .unwrap();
    let merged_state =
        MergedNetworkState::new(desired, current, Default::default(), false)
            .unwrap();

    let merged_iface =
        merged_state.interfaces.kernel_ifaces.get("eth1").unwrap();
    assert!(merged_iface.for_apply.is_none());
    assert!(merged_iface.for_verify.is_none());
    assert!(merged_iface.desired.is_none());
}
