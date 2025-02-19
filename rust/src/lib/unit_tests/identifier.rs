// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, Interface, Interfaces, MergedInterfaces};

#[test]
fn test_can_have_dup_profile_name_when_not_refered() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          profile-name: port1
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2A
        - name: dummy2
          profile-name: port1
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2B
        - name: port2
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2C
        - name: bond0
          type: bond
          state: up
          link-aggregation:
            mode: balance-rr
            port:
            - port2
        ",
    )
    .unwrap();

    let current = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2A
        - name: dummy2
          type: dummy
          state: up
          mac-address: 32:BB:72:65:19:2B
        - name: dummy3
          type: dummy
          state: up
          mac-address: 32:BB:72:65:19:2C
        ",
    )
    .unwrap();

    MergedInterfaces::new(desired, current, false, false).unwrap();
}

#[test]
fn test_port_refer_to_kernel_interface() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          type: dummy
          state: up
          mac-address: 32:BB:72:65:19:2A
        - name: dummy2
          profile-name: dummy1
          type: dummy
          state: up
          mac-address: 32:BB:72:65:19:2B
        - name: br0
          type: linux-bridge
          state: up
          bridge:
            ports:
            - name: dummy1
        ",
    )
    .unwrap();

    let mut merged =
        MergedInterfaces::new(desired, Interfaces::default(), false, false)
            .unwrap();

    let dummy1 = merged
        .kernel_ifaces
        .remove("dummy1")
        .unwrap()
        .for_apply
        .unwrap();

    assert_eq!(dummy1.name(), "dummy1");
    assert_eq!(dummy1.base_iface().controller.as_deref(), Some("br0"));
    assert!(dummy1.base_iface().identifier.as_ref().is_none());
    assert_eq!(
        dummy1.base_iface().mac_address.as_deref(),
        Some("32:BB:72:65:19:2A")
    );
}

#[test]
fn test_port_cannot_refer_to_interfaces_holding_profile_name() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: br0
          type: linux-bridge
          state: up
          bridge:
            ports:
            - name: port1
        ",
    )
    .unwrap();

    let current = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          profile-name: port1
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2A
        - name: dummy2
          profile-name: port1
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2B
        ",
    )
    .unwrap();

    let result = MergedInterfaces::new(desired, current, false, false);

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_port_ref_not_found() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: br0
          type: linux-bridge
          state: up
          bridge:
            ports:
            - name: port1
        ",
    )
    .unwrap();

    let current = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          profile-name: port2
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2A
        ",
    )
    .unwrap();

    let result = MergedInterfaces::new(desired, current, false, false);

    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_vlan_parent_ref_by_profile_name() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: vlan0
          type: vlan
          state: up
          vlan:
            base-iface: wan0
            id: 100
        ",
    )
    .unwrap();

    let current = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          profile-name: wan0
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2A
        ",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let merged_iface = merged_ifaces.kernel_ifaces.get("vlan0").unwrap();

    if let Interface::Vlan(vlan_iface) = merged_iface.desired.as_ref().unwrap()
    {
        assert_eq!(
            vlan_iface.vlan.as_ref().unwrap().base_iface.as_deref(),
            Some("dummy1")
        );
    } else {
        panic!("failed to find VLAN interface");
    }

    if let Interface::Vlan(vlan_iface) =
        merged_iface.for_apply.as_ref().unwrap()
    {
        assert_eq!(
            vlan_iface.vlan.as_ref().unwrap().base_iface.as_deref(),
            Some("dummy1")
        );
    } else {
        panic!("failed to find VLAN interface");
    }

    if let Interface::Vlan(vlan_iface) =
        merged_iface.for_verify.as_ref().unwrap()
    {
        assert_eq!(
            vlan_iface.vlan.as_ref().unwrap().base_iface.as_deref(),
            Some("dummy1")
        );
    } else {
        panic!("failed to find VLAN interface");
    }
}

#[test]
fn test_vxlan_parent_ref_by_profile_name() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: vxlan0
          type: vxlan
          state: up
          vxlan:
            base-iface: wan0
            id: 100
            remote: 192.0.2.251
            destination-port: 1235
        ",
    )
    .unwrap();

    let current = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          profile-name: wan0
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2A
        ",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let merged_iface = merged_ifaces.kernel_ifaces.get("vxlan0").unwrap();

    if let Interface::Vxlan(vxlan_iface) =
        merged_iface.for_apply.as_ref().unwrap()
    {
        assert_eq!(
            vxlan_iface.vxlan.as_ref().unwrap().base_iface.as_str(),
            "dummy1"
        );
    } else {
        panic!("failed to find VxLAN interface");
    }
}

#[test]
fn test_macsec_parent_ref_by_profile_name() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
- name: macsec0
  type: macsec
  state: up
  macsec:
    encrypt: true
    base-iface: wan0
    mka-cak: 50b71a8ef0bd5751ea76de6d6c98c03a
    mka-ckn: f2b4297d39da7330910a74abc0449feb45b5c0b9fc23df1430e1898fcf1c4550
    port: 0
    validation: strict
    send-sci: true
    offload: off",
    )
    .unwrap();

    let current = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          profile-name: wan0
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2A
        ",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let merged_iface = merged_ifaces.kernel_ifaces.get("macsec0").unwrap();

    if let Interface::MacSec(macsec_iface) =
        merged_iface.for_apply.as_ref().unwrap()
    {
        assert_eq!(
            macsec_iface.macsec.as_ref().unwrap().base_iface.as_str(),
            "dummy1"
        );
    } else {
        panic!("failed to find MacSec interface");
    }
}

#[test]
fn test_macvlan_parent_ref_by_profile_name() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: macvlan0
          type: mac-vlan
          state: up
          mac-vlan:
            base-iface: wan0
            mode: passthru",
    )
    .unwrap();

    let current = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          profile-name: wan0
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2A
        ",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let merged_iface = merged_ifaces.kernel_ifaces.get("macvlan0").unwrap();

    if let Interface::MacVlan(mac_vlan_iface) =
        merged_iface.for_apply.as_ref().unwrap()
    {
        assert_eq!(
            mac_vlan_iface
                .mac_vlan
                .as_ref()
                .unwrap()
                .base_iface
                .as_str(),
            "dummy1"
        );
    } else {
        panic!("failed to find MacSec interface");
    }
}

#[test]
fn test_macvtap_parent_ref_by_profile_name() {
    let desired = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: macvtap0
          type: mac-vtap
          state: up
          mac-vtap:
            base-iface: wan0
            mode: passthru",
    )
    .unwrap();

    let current = serde_yaml::from_str::<Interfaces>(
        r"---
        - name: dummy1
          profile-name: wan0
          type: dummy
          state: up
          identifier: mac-address
          mac-address: 32:BB:72:65:19:2A
        ",
    )
    .unwrap();

    let merged_ifaces =
        MergedInterfaces::new(desired, current, false, false).unwrap();

    let merged_iface = merged_ifaces.kernel_ifaces.get("macvtap0").unwrap();

    if let Interface::MacVtap(mac_vtap_iface) =
        merged_iface.for_apply.as_ref().unwrap()
    {
        assert_eq!(
            mac_vtap_iface
                .mac_vtap
                .as_ref()
                .unwrap()
                .base_iface
                .as_str(),
            "dummy1"
        );
    } else {
        panic!("failed to find MacSec interface");
    }
}
