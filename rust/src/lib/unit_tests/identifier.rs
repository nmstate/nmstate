// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, Interfaces, MergedInterfaces};

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
