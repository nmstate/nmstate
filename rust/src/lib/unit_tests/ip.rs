// SPDX-License-Identifier: Apache-2.0

use crate::{
    BaseInterface, ErrorKind, Interface, InterfaceIpv6, InterfaceState,
    Interfaces, MergedInterfaces, RouteEntry, ip::sanitize_ip_network,
    unit_tests::testlib::new_eth_iface,
};

fn gen_test_eth_ifaces() -> Interfaces {
    let mut ifaces = Interfaces::new();
    ifaces.push(new_eth_iface("eth1"));
    ifaces
}

#[test]
fn test_ip_stringlized_attributes() {
    let iface: BaseInterface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: up
ipv4:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "192.168.1.1"
    prefix-length: "24"
ipv6:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
    prefix-length: "64"
"#,
    )
    .unwrap();
    let ipv4_conf = iface.ipv4.unwrap();
    let ipv6_conf = iface.ipv6.unwrap();

    assert!(ipv4_conf.enabled);
    assert_eq!(ipv4_conf.dhcp, Some(false));
    assert_eq!(
        ipv4_conf.addresses.as_deref().unwrap()[0].ip.to_string(),
        "192.168.1.1"
    );
    assert_eq!(ipv4_conf.addresses.as_deref().unwrap()[0].prefix_length, 24);
    assert!(ipv6_conf.enabled);
    assert_eq!(
        ipv6_conf.addresses.as_deref().unwrap()[0].ip.to_string(),
        "2001:db8:85a3::8a2e:370:7331",
    );
    assert_eq!(ipv6_conf.addresses.as_deref().unwrap()[0].prefix_length, 64);
}

#[test]
fn test_ip_ignore_deserialize_error_of_absent_iface() {
    let iface: Interface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: absent
ipv4:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "g.g.g.g"
    prefix-length: "24"
ipv6:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "::g"
    prefix-length: "64"
"#,
    )
    .unwrap();
    assert_eq!(iface.base_iface().state, InterfaceState::Absent);
    assert_eq!(iface.name(), "eth1");
    assert_eq!(iface.base_iface().ipv4, None);
    assert_eq!(iface.base_iface().ipv6, None);
}

#[test]
fn test_ip_allow_extra_address_by_default() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv4:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "192.168.1.1"
      prefix-length: "24"
  ipv6:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
      prefix-length: "64"
"#,
    )
    .unwrap();
    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv4:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "192.168.1.1"
      prefix-length: "24"
    - ip: "192.168.1.2"
      prefix-length: "24"
  ipv6:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
      prefix-length: "64"
    - ip: "2001:0db8:85a3:0000:0001:8a2e:0370:7331"
      prefix-length: "64"
"#,
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        desired,
        gen_test_eth_ifaces(),
        Default::default(),
        false,
    )
    .unwrap();

    merged_ifaces.verify(&current).unwrap();
}

#[test]
fn test_ipv4_not_allow_extra_address() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv4:
    enabled: "true"
    dhcp: "false"
    allow-extra-address: false
    address:
    - ip: "192.168.1.1"
      prefix-length: "24"
"#,
    )
    .unwrap();
    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv4:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "192.168.1.1"
      prefix-length: "24"
    - ip: "192.168.1.2"
      prefix-length: "24"
"#,
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        desired,
        gen_test_eth_ifaces(),
        Default::default(),
        false,
    )
    .unwrap();

    let result = merged_ifaces.verify(&current);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::VerificationError);
    }
}

#[test]
fn test_ipv6_not_allow_extra_address() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv6:
    enabled: "true"
    dhcp: "false"
    allow-extra-address: false
    address:
    - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
      prefix-length: "64"
"#,
    )
    .unwrap();
    let current: Interfaces = serde_yaml::from_str(
        r#"---
- name: eth1
  type: ethernet
  state: up
  ipv6:
    enabled: "true"
    dhcp: "false"
    address:
    - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
      prefix-length: "64"
    - ip: "2001:0db8:85a3:0000:0001:8a2e:0370:7331"
      prefix-length: "64"
"#,
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        desired,
        gen_test_eth_ifaces(),
        Default::default(),
        false,
    )
    .unwrap();

    let result = merged_ifaces.verify(&current);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::VerificationError);
    }
}

#[test]
fn test_ipv6_mtu_lower_than_1280() {
    let mut iface: BaseInterface = serde_yaml::from_str(
        r#"---
name: eth1
type: ethernet
state: up
mtu: 1279
ipv6:
  enabled: "true"
  dhcp: "false"
  address:
  - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
    prefix-length: "64"
"#,
    )
    .unwrap();

    let result = iface.sanitize(true);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
        assert!(e.msg().contains("MTU should be >= 1280"));
    }
}

#[test]
fn test_ipv6_verify_emtpy() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
            - name: eth1
              type: ethernet
              state: up
              ipv6:
                enabled: "true"
                dhcp: "false"
                address: []"#,
    )
    .unwrap();

    let cur_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
            - name: eth1
              type: ethernet
              state: up
              ipv6:
                enabled: "true"
                dhcp: "false""#,
    )
    .unwrap();

    let merged_ifaces = MergedInterfaces::new(
        des_ifaces,
        gen_test_eth_ifaces(),
        Default::default(),
        false,
    )
    .unwrap();

    merged_ifaces.verify(&cur_ifaces).unwrap();
}

#[test]
fn test_should_not_have_ipv6_in_ipv4_section() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
            - name: eth1
              type: ethernet
              state: up
              ipv4:
                enabled: "true"
                dhcp: "false"
                address:
                  - ip: "2001:db8:2::1"
                    prefix-length: 64"#,
    )
    .unwrap();

    let result = MergedInterfaces::new(
        des_ifaces,
        gen_test_eth_ifaces(),
        Default::default(),
        false,
    );
    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_should_not_have_ipv4_in_ipv6_section() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
            - name: eth1
              type: ethernet
              state: up
              ipv6:
                enabled: true
                dhcp: false
                address:
                  - ip: 192.0.2.1
                    prefix-length: 24",
    )
    .unwrap();

    let result = MergedInterfaces::new(
        des_ifaces,
        gen_test_eth_ifaces(),
        Default::default(),
        false,
    );
    assert!(result.is_err());

    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_ipv4_verify_valid_prefix() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r"---
            - name: eth1
              type: ethernet
              state: up
              ipv4:
                enabled: true
                dhcp: false
                address:
                  - ip: 192.0.2.1
                    prefix-length: 33",
    )
    .unwrap();

    let result = MergedInterfaces::new(
        des_ifaces,
        gen_test_eth_ifaces(),
        Default::default(),
        false,
    );

    assert!(result.is_err());
    assert_eq!(result.unwrap_err().kind(), ErrorKind::InvalidArgument);
}

#[test]
fn test_ipv6_verify_valid_prefix() {
    let des_ifaces: Interfaces = serde_yaml::from_str(
        r#"---
            - name: eth1
              type: ethernet
              state: up
              ipv6:
                enabled: true
                dhcp: false
                address:
                  - ip: "2001:db8:2::1"
                    prefix-length: 129"#,
    )
    .unwrap();

    let result = MergedInterfaces::new(
        des_ifaces,
        gen_test_eth_ifaces(),
        Default::default(),
        false,
    );

    assert!(result.is_err());
    assert_eq!(result.unwrap_err().kind(), ErrorKind::InvalidArgument);
}

#[test]
fn test_sanitize_ip_network_empty_str() {
    let result = sanitize_ip_network("");
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_sanitize_ip_network_invalid_str() {
    let result = sanitize_ip_network("192.0.2.1/24/");
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_sanitize_ip_network_invalid_ipv4_prefix_length() {
    let result = sanitize_ip_network("192.0.2.1/33");
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_sanitize_ip_network_invalid_ipv6_prefix_length() {
    let result = sanitize_ip_network("::1/129");
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::InvalidArgument);
    }
}

#[test]
fn test_sanitize_ip_network_ipv4_gateway() {
    assert_eq!(sanitize_ip_network("0.0.0.1/0").unwrap(), "0.0.0.0/0");
}

#[test]
fn test_sanitize_ip_network_ipv6_gateway() {
    assert_eq!(sanitize_ip_network("::1/0").unwrap(), "::/0");
}

#[test]
fn test_sanitize_ip_network_ipv4_host_only() {
    assert_eq!(sanitize_ip_network("192.0.2.1").unwrap(), "192.0.2.1/32");
}

#[test]
fn test_sanitize_ip_network_ipv6_host_only() {
    assert_eq!(
        sanitize_ip_network("2001:db8:1::0").unwrap(),
        "2001:db8:1::/128"
    );
}

#[test]
fn test_sanitize_ip_network_ipv4_host_only_explicit() {
    assert_eq!(sanitize_ip_network("192.0.2.1/32").unwrap(), "192.0.2.1/32");
}

#[test]
fn test_sanitize_ip_network_ipv6_host_only_explicit() {
    assert_eq!(
        sanitize_ip_network("2001:db8:1::0/128").unwrap(),
        "2001:db8:1::/128"
    );
}

#[test]
fn test_sanitize_ip_network_ipv4_net() {
    assert_eq!(sanitize_ip_network("192.0.3.1/23").unwrap(), "192.0.2.0/23");
}

#[test]
fn test_sanitize_ip_network_ipv6_net() {
    assert_eq!(
        sanitize_ip_network("2001:db8:1::f/64").unwrap(),
        "2001:db8:1::/64"
    );
}

#[test]
fn test_auto_ip_lift_time() {
    let left_fmt: BaseInterface = serde_yaml::from_str(
        r#"---
        name: eth1
        type: ethernet
        state: up
        ipv4:
          enabled: "true"
          dhcp: "false"
          address:
          - ip: "192.168.1.1"
            prefix-length: "24"
            valid-left: "60sec"
            preferred-left: "60sec"
        ipv6:
          enabled: "true"
          dhcp: "false"
          address:
          - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
            prefix-length: "64"
            valid-left: "60sec"
            preferred-left: "60sec"
        "#,
    )
    .unwrap();
    let life_time_fmt: BaseInterface = serde_yaml::from_str(
        r#"---
        name: eth1
        type: ethernet
        state: up
        ipv4:
          enabled: "true"
          dhcp: "false"
          address:
          - ip: "192.168.1.1"
            prefix-length: "24"
            valid-life-time: "60sec"
            preferred-life-time: "60sec"
        ipv6:
          enabled: "true"
          dhcp: "false"
          address:
          - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
            prefix-length: "64"
            valid-life-time: "60sec"
            preferred-life-time: "60sec"
        "#,
    )
    .unwrap();

    let iproute_fmt: BaseInterface = serde_yaml::from_str(
        r#"---
        name: eth1
        type: ethernet
        state: up
        ipv4:
          enabled: "true"
          dhcp: "false"
          address:
          - ip: "192.168.1.1"
            prefix-length: "24"
            valid-lft: "60sec"
            preferred-lft: "60sec"
        ipv6:
          enabled: "true"
          dhcp: "false"
          address:
          - ip: "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
            prefix-length: "64"
            valid-lft: "60sec"
            preferred-lft: "60sec"
        "#,
    )
    .unwrap();

    assert_eq!(left_fmt, life_time_fmt);
    assert_eq!(iproute_fmt, life_time_fmt);
}

#[test]
fn test_ip_serlize_allow_extra_address() {
    let desired: Interfaces = serde_yaml::from_str(
        r#"---
        - name: eth1
          type: ethernet
          state: up
          ipv4:
            enabled: "true"
            dhcp: "false"
            allow-extra-address: false
          ipv6:
            enabled: "true"
            dhcp: "false"
        "#,
    )
    .unwrap();

    let new: Interfaces =
        serde_yaml::from_str(&serde_yaml::to_string(&desired).unwrap())
            .unwrap();

    assert_eq!(desired, new);
}

#[test]
fn test_forwarding_ipv6_deserialize_error() {
    let desired = r#"---
name: eth1
type: ethernet
state: up
ipv6:
  enabled: true
  dhcp: false
  autoconf: false
  forwarding: true
  address:
  - ip: 2001:db8:1::1
    prefix-length: 64
"#;

    let value = serde_yaml::from_str::<serde_yaml::Value>(desired).unwrap();

    let result = serde_json::from_value::<Interface>(
        serde_json::to_value(value).unwrap(),
    );

    assert!(result.is_err());

    let err = result.unwrap_err();
    let err_str = err.to_string();

    assert!(err_str.starts_with("InvalidArgument:"));
}

#[test]
fn test_no_error_on_diff_auto_metric_without_dhcpv4() {
    let mut iface: Interface = serde_yaml::from_str(
        r#"---
        name: eth1
        type: ethernet
        state: up
        ipv4:
          enabled: true
          dhcp: false
          auto-route-metric: 100
          prefix-route-metric: 101"#,
    )
    .unwrap();

    iface.sanitize(true).unwrap();
}

#[test]
fn test_no_error_on_diff_auto_metric_if_one_is_default() {
    for (auto_metric, prefix_metric) in [
        (RouteEntry::USE_DEFAULT_METRIC, 101),
        (101, RouteEntry::USE_DEFAULT_METRIC),
    ] {
        let mut iface: Interface = serde_yaml::from_str(&format!(
            r#"---
            name: eth1
            type: ethernet
            state: up
            ipv4:
              enabled: true
              dhcp: true
              auto-route-metric: {auto_metric}
              prefix-route-metric: {prefix_metric}"#,
        ))
        .unwrap();

        iface.sanitize(true).unwrap();

        let base_iface = iface.base_iface();

        assert_eq!(
            base_iface.ipv4.as_ref().and_then(|i| i.auto_route_metric),
            Some(101)
        );
        assert_eq!(
            base_iface.ipv4.as_ref().and_then(|i| i.prefix_route_metric),
            Some(101)
        );
    }
}

#[test]
fn test_error_on_diff_auto_metric_with_dhcpv4() {
    let mut iface: Interface = serde_yaml::from_str(
        r#"---
        name: eth1
        type: ethernet
        state: up
        ipv4:
          enabled: true
          dhcp: true
          auto-route-metric: 100
          prefix-route-metric: 101"#,
    )
    .unwrap();

    let error = iface.sanitize(true).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::NotSupportedError);
    assert!(error.msg().contains("Different"));
    assert!(error.msg().contains("ipv4.auto-route-metric"));
    assert!(error.msg().contains("ipv4.prefix-route-metric"));
}

#[test]
fn test_error_on_route_metric_out_of_range() {
    for prop_name in ["auto-route-metric", "prefix-route-metric"] {
        for invalid_value in [-2i64, u32::MAX as i64 + 1] {
            let mut iface: Interface = serde_yaml::from_str(&format!(
                r#"---
                name: eth1
                type: ethernet
                state: up
                ipv4:
                  enabled: true
                  dhcp: true
                  {prop_name}: {invalid_value}"#
            ))
            .unwrap();

            let error = iface.sanitize(true).unwrap_err();
            assert_eq!(error.kind(), ErrorKind::InvalidArgument);
            assert!(error.msg().contains("Invalid value"));
            assert!(error.msg().contains(&format!("ipv4.{prop_name}")));
        }
    }
}

#[test]
fn test_disable_ipv6_where_all() {
    let mut ifaces = Interfaces::new();

    let mut eth1 = new_eth_iface("eth1");
    eth1.base_iface_mut().ipv6 = Some(InterfaceIpv6 {
        enabled: true,
        enabled_defined: false,
        dhcp: Some(true),
        autoconf: Some(true),
        ..Default::default()
    });
    ifaces.push(eth1);

    // no IPv6 section: must stay None, not be synthesised
    ifaces.push(new_eth_iface("eth2"));

    ifaces.disable_ipv6_where(|_| true);

    let eth1_ipv6 = ifaces
        .get_iface("eth1", crate::InterfaceType::Ethernet)
        .unwrap()
        .base_iface()
        .ipv6
        .as_ref()
        .unwrap();
    assert!(!eth1_ipv6.enabled);
    assert!(eth1_ipv6.enabled_defined);
    assert_eq!(eth1_ipv6.dhcp, None);
    assert_eq!(eth1_ipv6.autoconf, None);

    assert!(
        ifaces
            .get_iface("eth2", crate::InterfaceType::Ethernet)
            .unwrap()
            .base_iface()
            .ipv6
            .is_none()
    );
}
