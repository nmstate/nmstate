// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, Interfaces, MergedInterfaces};

#[test]
fn test_hsr_port_cannot_have_ip_enabled_explicitly() {
    let des_ifaces: Interfaces = rmsd_yaml::from_str(
        r"---
        - name: hsr0
          type: hsr
          state: up
          hsr:
            port1: eth1
            port2: eth2
            protocol: prp
            multicast-spec: 40
        - name: eth1
          type: ethernet
          state: up
          ipv4:
            enabled: true
            dhcp: true
          ipv6:
            enabled: true
            dhcp: true
            autoconf: true",
    )
    .unwrap();
    let cur_ifaces: Interfaces = rmsd_yaml::from_str(
        r"---
        - name: eth1
          type: ethernet
        - name: eth2
          type: ethernet
        ",
    )
    .unwrap();

    let result = MergedInterfaces::new(
        des_ifaces,
        cur_ifaces,
        Default::default(),
        false,
    );

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("hsr0"));
        assert!(e.msg().contains("eth1"));
    }
}

#[test]
fn test_auto_include_hsr_port_as_changed() {
    let des_ifaces: Interfaces = rmsd_yaml::from_str(
        r"---
        - name: hsr0
          type: hsr
          state: up
          hsr:
            port1: eth1
            port2: eth2
            protocol: prp
            multicast-spec: 40",
    )
    .unwrap();
    let cur_ifaces: Interfaces = rmsd_yaml::from_str(
        r"---
        - name: eth1
          type: ethernet
          ipv4:
            enabled: true
            dhcp: true
          ipv6:
            enabled: true
            dhcp: true
            autoconf: true
        - name: eth2
          type: ethernet
          ipv4:
            enabled: true
            dhcp: true
          ipv6:
            enabled: true
            dhcp: true
            autoconf: true
        ",
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        cur_ifaces,
        Default::default(),
        false,
    )
    .unwrap();

    let port1 = merged_ifaces.kernel_ifaces["eth1"]
        .for_apply
        .as_ref()
        .unwrap();
    let port2 = merged_ifaces.kernel_ifaces["eth2"]
        .for_apply
        .as_ref()
        .unwrap();

    assert_eq!(
        port1.base_iface().ipv4.as_ref().map(|i| i.enabled),
        Some(false)
    );
    assert_eq!(
        port1.base_iface().ipv6.as_ref().map(|i| i.enabled),
        Some(false)
    );
    assert_eq!(
        port2.base_iface().ipv4.as_ref().map(|i| i.enabled),
        Some(false)
    );
    assert_eq!(
        port2.base_iface().ipv6.as_ref().map(|i| i.enabled),
        Some(false)
    );
}

#[test]
fn test_prp_interlink_is_forbidden() {
    let cur_ifaces: Interfaces = rmsd_yaml::from_str(
        r"---
      - name: eth1
        type: ethernet
      - name: eth2
        type: ethernet
      - name: eth3
        type: ethernet
      ",
    )
    .unwrap();
    let des_ifaces = rmsd_yaml::from_str(
        r"---
        - name: hsr0
          type: hsr
          state: up
          hsr:
            port1: eth1
            port2: eth2
            interlink: eth3
            protocol: prp
            multicast-spec: 40",
    )
    .unwrap();

    let err = MergedInterfaces::new(
        des_ifaces,
        cur_ifaces,
        Default::default(),
        false,
    )
    .unwrap_err();

    assert_eq!(err.kind(), ErrorKind::InvalidArgument);
    assert!(err.msg().contains("interlink property is not supported"));
}

#[test]
fn test_hsr_deny_unknown_config_field() {
    let result = rmsd_yaml::from_str::<Interfaces>(
        r"---
        - name: hsr0
          type: hsr
          state: up
          hsr:
            port1: eth1
            port2: eth2
            multicast-specc: 40
        ",
    );
    let err = result.unwrap_err().to_string();
    assert!(err.contains("unknown field"));
    assert!(err.contains("multicast-specc"));
}
