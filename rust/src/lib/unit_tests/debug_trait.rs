// SPDX-License-Identifier: Apache-2.0

use crate::{Interface, NetworkState};

#[test]
fn test_debug_trait() {
    let ethernet = serde_yaml::from_str(
        r"
        name: eth1
        type: ethernet
        state: up
        802.1x:
            ca-cert: /etc/pki/802-1x-test/ca.crt
            client-cert: /etc/pki/802-1x-test/client.example.org.crt
            eap-methods:
                - tls
            identity: client.example.org
            private-key: /etc/pki/802-1x-test/client.example.org.key
            private-key-password: A1234567890
        ",
    )
    .unwrap();

    let des_eth = Interface::base_iface(&ethernet);

    let mut net_state = NetworkState::new();
    net_state.interfaces.push(ethernet.clone());

    let debug_tr_eth = format!("{:?}", &des_eth);
    let debug_tr_net_state = format!("{:?}", &net_state);

    let password_hid_by_nmstate =
        format!("private_key_password: Some(\"<_password_hid_by_nmstate>\")");

    assert_ne!(
        des_eth.ieee8021x.as_ref().unwrap().private_key_password,
        Some("A123456789000".to_string())
    );
    assert_eq!(
        des_eth.ieee8021x.as_ref().unwrap().private_key_password,
        Some("A1234567890".to_string())
    );
    assert!(debug_tr_eth.contains(&password_hid_by_nmstate));
    assert!(debug_tr_net_state.contains(&password_hid_by_nmstate));
}
