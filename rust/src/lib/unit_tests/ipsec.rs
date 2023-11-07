// SPDX-License-Identifier: Apache-2.0

use crate::NetworkState;

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
