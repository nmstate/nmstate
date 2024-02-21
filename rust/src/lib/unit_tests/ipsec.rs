// SPDX-License-Identifier: Apache-2.0

use crate::{IpsecInterface, NetworkState};

#[test]
fn test_ipsec_hide_psk() {
    let mut state: NetworkState = serde_yaml::from_str(
        r"---
        interfaces:
        - name: hosta_conn
          type: ipsec
          state: up
          wait-ip: any
          ipv4:
            enabled: true
            dhcp: true
            dhcp-client-id: ll
            auto-dns: true
            auto-gateway: true
            auto-routes: true
            auto-route-table-id: 0
            dhcp-send-hostname: true
          ipv6:
            enabled: false
            dhcp: false
            autoconf: false
          lldp:
            enabled: false
          libreswan:
            right: 192.0.2.253
            rightid: '@hostb-psk.example.org'
            left: 192.0.2.250
            leftid: '@hosta-psk.example.org'
            ikev2: insist
            psk: TOP_SECRET",
    )
    .unwrap();

    state.hide_secrets();
    assert!(!serde_yaml::to_string(&state)
        .unwrap()
        .contains("TOP_SECRET"));
}

#[test]
fn test_invalid_ipsec_interface_value() {
    let result = serde_yaml::from_str::<NetworkState>(
        r"---
        interfaces:
        - name: hosta_conn
          type: ipsec
          state: up
          libreswan:
            ipsec-interface: true
            right: 192.0.2.253
            rightid: '@hostb-psk.example.org'
            left: 192.0.2.250
            leftid: '@hosta-psk.example.org'
            ikev2: insist
            psk: TOP_SECRET",
    );
    assert!(result.is_err());

    if let Err(e) = result {
        assert!(e.to_string().contains("Invalid ipsec-interface value"))
    }
}

#[test]
fn test_parse_ipsec_interface_from_string_interger() {
    let iface = serde_yaml::from_str::<IpsecInterface>(
        r"---
          name: hosta_conn
          type: ipsec
          state: up
          libreswan:
            ipsec-interface: '99'
            right: 192.0.2.253
            rightid: '@hostb-psk.example.org'
            left: 192.0.2.250
            leftid: '@hosta-psk.example.org'
            ikev2: insist
            psk: TOP_SECRET",
    )
    .unwrap();

    assert_eq!(
        iface.libreswan.as_ref().unwrap().ipsec_interface.as_deref(),
        Some("99")
    );
}

#[test]
fn test_parse_ipsec_interface_from_interger() {
    let iface = serde_yaml::from_str::<IpsecInterface>(
        r"---
          name: hosta_conn
          type: ipsec
          state: up
          libreswan:
            ipsec-interface: 99
            right: 192.0.2.253
            rightid: '@hostb-psk.example.org'
            left: 192.0.2.250
            leftid: '@hosta-psk.example.org'
            ikev2: insist
            psk: TOP_SECRET",
    )
    .unwrap();

    assert_eq!(
        iface.libreswan.as_ref().unwrap().ipsec_interface.as_deref(),
        Some("99")
    );
}

#[test]
fn test_parse_ipsec_interface_from_string_bool() {
    let iface = serde_yaml::from_str::<IpsecInterface>(
        r"---
          name: hosta_conn
          type: ipsec
          state: up
          libreswan:
            ipsec-interface: 'no'
            right: 192.0.2.253
            rightid: '@hostb-psk.example.org'
            left: 192.0.2.250
            leftid: '@hosta-psk.example.org'
            ikev2: insist
            psk: TOP_SECRET",
    )
    .unwrap();

    assert_eq!(
        iface.libreswan.as_ref().unwrap().ipsec_interface.as_deref(),
        Some("no")
    );
}

#[test]
fn test_ipsec_treat_dhcp_off_and_empty_ip_as_disabled() {
    let mut iface = serde_yaml::from_str::<IpsecInterface>(
        r"---
          name: hosta_conn
          type: ipsec
          state: up
          ipv4:
            enabled: true
            dhcp: false
          libreswan:
            ipsec-interface: 'no'
            right: 192.0.2.253
            rightid: '@hostb-psk.example.org'
            left: 192.0.2.250
            leftid: '@hosta-psk.example.org'
            ikev2: insist
            psk: TOP_SECRET",
    )
    .unwrap();

    iface.sanitize(false);

    assert!(!iface.base.ipv4.as_ref().unwrap().enabled);
}
