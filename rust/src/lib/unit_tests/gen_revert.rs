// SPDX-License-Identifier: Apache-2.0

use crate::{MergedNetworkState, NetworkState, NetworkStateMode, RouteState};

const TEST_DATA_FOLDER_PATH: &str = "unit_tests/gen_revert_test_files";
const DESIRED_FILE_NAME: &str = "desired.yml";
const CURRENT_FILE_NAME: &str = "current.yml";
const REVERT_FILE_NAME: &str = "revert.yml";

#[test]
fn test_gen_revert() {
    let folded_path =
        std::path::Path::new(&std::env::var("CARGO_MANIFEST_DIR").unwrap())
            .join(TEST_DATA_FOLDER_PATH);

    for entry in std::fs::read_dir(folded_path).unwrap() {
        let entry = entry.unwrap();
        let path = entry.path();
        let current = load_state(&path.join(CURRENT_FILE_NAME));
        let desired = load_state(&path.join(DESIRED_FILE_NAME));
        let expected_revert =
            serde_yaml::to_string(&load_state(&path.join(REVERT_FILE_NAME)))
                .unwrap();
        let revert =
            serde_yaml::to_string(&desired.generate_revert(&current).unwrap())
                .unwrap();
        if expected_revert != revert {
            panic!(
                "FAIL: {:?}\nExpected:\n\n{}\nGot:\n\n{}",
                entry.file_name(),
                expected_revert,
                revert
            );
        }
        println!("PASS: {:?}", entry.file_name());
    }
}

fn load_state(file_path: &std::path::Path) -> NetworkState {
    let fd = std::fs::File::open(file_path).unwrap();
    match serde_yaml::from_reader(fd) {
        Ok(n) => n,
        Err(e) => {
            panic!("FAIL to load NetworkState from {file_path:?}: {e}");
        }
    }
}

#[test]
fn test_gen_revert_keeps_existing_route_and_rule() {
    let current: NetworkState = serde_yaml::from_str(
        r#"
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          ipv4:
            enabled: true
        routes:
          config:
          - destination: 198.51.100.0/24
            next-hop-interface: eth1
            next-hop-address: 192.0.2.1
            metric: 50
            table-id: 254
          - destination: 203.0.113.0/24
            next-hop-interface: eth1
            next-hop-address: 0.0.0.0
        route-rules:
          config:
          - ip-from: 192.0.2.10/32
            route-table: 254
            priority: 1000
          - family: ipv4
            action: blackhole
            route-table: 254
            priority: 1001
        "#,
    )
    .unwrap();
    let mut desired = NetworkState {
        routes: current.routes.clone(),
        rules: current.rules.clone(),
        ..Default::default()
    };

    let diff = desired.gen_diff(&current).unwrap();
    assert!(diff.routes.config.is_none());
    assert!(diff.rules.config.is_none());

    let revert = desired.generate_revert(&current).unwrap();
    assert!(revert.routes.config.is_none());
    assert!(revert.rules.config.is_none());

    let routes = desired.routes.config.as_mut().unwrap();
    routes[0].table_id = None;
    routes[0].metric = None;
    routes[1].next_hop_addr = None;
    for rule in desired.rules.config.as_mut().unwrap() {
        rule.table_id = None;
        rule.priority = None;
    }

    let revert = desired.generate_revert(&current).unwrap();
    assert!(revert.routes.config.is_none());
    assert!(revert.rules.config.is_none());

    // An explicit removal and re-addition with a different metric
    // replaces the route even when the other route properties match.
    let route = &mut desired.routes.config.as_mut().unwrap()[0];
    route.metric = Some(20);
    let mut absent = route.clone();
    absent.state = Some(RouteState::Absent);
    absent.metric = Some(50);
    desired.routes.config.as_mut().unwrap().push(absent);

    let revert = desired.generate_revert(&current).unwrap();
    let routes = revert.routes.config.as_ref().unwrap();
    assert_eq!(routes.len(), 2);
    assert!(routes[0].is_absent());
    assert_eq!(routes[0].metric, Some(20));
    assert!(!routes[1].is_absent());
    assert_eq!(routes[1].metric, Some(50));
}

#[test]
fn test_gen_revert_restores_routes_with_distinct_metrics() {
    let mut current: NetworkState = serde_yaml::from_str(
        r#"
        routes:
          config:
          - destination: 198.51.100.0/24
            route-type: blackhole
            metric: 100
            table-id: 99
          - destination: 198.51.100.0/24
            route-type: blackhole
            metric: 200
            table-id: 99
          - destination: 198.51.100.0/24
            route-type: blackhole
            metric: 300
            table-id: 99
        "#,
    )
    .unwrap();
    let mut desired = current.clone();
    let entries = desired.routes.config.as_mut().unwrap();
    entries.truncate(2);
    entries[1].state = Some(RouteState::Absent);
    entries[1].metric = None;

    for _ in 0..2 {
        let revert = desired.generate_revert(&current).unwrap();
        let routes = revert.routes.config.as_ref().unwrap();
        assert!(routes.iter().all(|rt| !rt.is_absent()));
        assert_eq!(
            routes.iter().map(|r| r.metric.unwrap()).collect::<Vec<_>>(),
            [200, 300]
        );

        // Apply the serialized revert through the same route merge that the
        // NetworkManager backend uses to choose the routes to configure.
        let forward = MergedNetworkState::new(
            desired.clone(),
            current.clone(),
            NetworkStateMode::default(),
            false,
        )
        .unwrap();
        let mut updated = current.clone();
        updated.routes.config = Some(forward.routes.merged["lo"].clone());
        assert_eq!(updated.routes.config.as_ref().unwrap().len(), 1);
        assert_eq!(
            updated.routes.config.as_ref().unwrap()[0].metric,
            Some(100)
        );
        let revert =
            serde_yaml::from_str(&serde_yaml::to_string(&revert).unwrap())
                .unwrap();
        let restored = MergedNetworkState::new(
            revert,
            updated,
            NetworkStateMode::default(),
            false,
        )
        .unwrap();
        let routes = &restored.routes.merged["lo"];
        assert_eq!(
            routes.iter().map(|r| r.metric.unwrap()).collect::<Vec<_>>(),
            [100, 200, 300]
        );
        #[cfg(feature = "gen_conf")]
        {
            let keyfiles = current.gen_conf().unwrap();
            for metric in [100, 200, 300] {
                assert!(keyfiles["NetworkManager"].iter().any(
                    |(_, config)| {
                        config.lines().any(|line| {
                            line.ends_with(&format!(",{metric}"))
                                && line.starts_with("route")
                        })
                    }
                ));
            }
        }
        current.routes.config.as_mut().unwrap().reverse();
    }
}

#[test]
fn test_route_diff_and_revert_select_default_metric_without_matching_peers() {
    let current: NetworkState = serde_yaml::from_str(
        r#"
        routes:
          config:
          - destination: 198.51.100.0/24
            route-type: blackhole
          - destination: 198.51.100.0/24
            route-type: blackhole
            metric: 100
        "#,
    )
    .unwrap();
    let mut desired = current.clone();
    let entries = desired.routes.config.as_mut().unwrap();
    entries.truncate(1);
    entries[0].state = Some(RouteState::Absent);
    entries[0].metric = Some(0);

    let diff = desired.gen_diff(&current).unwrap();
    assert_eq!(diff.routes.config.as_ref().unwrap()[0].metric, Some(0));
    let updated = MergedNetworkState::new(
        diff,
        current.clone(),
        NetworkStateMode::default(),
        false,
    )
    .unwrap();
    let routes = &updated.routes.merged["lo"];
    assert_eq!(routes.len(), 1);
    assert_eq!(routes[0].metric, Some(100));

    let revert = desired.generate_revert(&current).unwrap();
    let mut updated = current;
    updated.routes.config = Some(routes.clone());
    let restored = MergedNetworkState::new(
        revert,
        updated,
        NetworkStateMode::default(),
        false,
    )
    .unwrap();
    let routes = &restored.routes.merged["lo"];
    assert_eq!(routes.len(), 2);
    assert_eq!(routes[0].metric, Some(0));
    assert_eq!(routes[1].metric, Some(100));
}

#[test]
fn test_gen_revert_compares_vrf_routes_by_resolved_table() {
    let with_vrf: NetworkState = serde_yaml::from_str(
        r#"
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          ipv4:
            enabled: true
        - name: vrf0
          type: vrf
          state: up
          vrf:
            port: [eth1]
            route-table-id: 100
        routes:
          config:
          - destination: 198.51.100.0/24
            next-hop-interface: eth1
            next-hop-address: 192.0.2.1
            table-id: 100
            vrf-name: vrf0
        "#,
    )
    .unwrap();
    let mut with_table = with_vrf.clone();
    with_table.routes.config.as_mut().unwrap()[0].vrf_name = None;
    let mut with_vrf_only = with_vrf.clone();
    with_vrf_only.routes.config.as_mut().unwrap()[0].table_id = None;

    for (desired, current) in [
        (&with_table, &with_vrf),
        (&with_vrf_only, &with_table),
        (&with_table, &with_vrf_only),
    ] {
        assert!(
            desired
                .generate_revert(current)
                .unwrap()
                .routes
                .config
                .is_none()
        );
        assert!(desired.gen_diff(current).unwrap().routes.config.is_none());
        let mut remove = desired.clone();
        remove.routes.config.as_mut().unwrap()[0].state =
            Some(RouteState::Absent);
        let revert = remove.generate_revert(current).unwrap();
        assert!(!revert.routes.config.as_ref().unwrap()[0].is_absent());
        assert_eq!(
            revert.routes.config.as_ref().unwrap()[0].table_id,
            Some(100)
        );
    }

    let mut before_vrf = NetworkState::new();
    before_vrf.interfaces.push(
        with_vrf
            .interfaces
            .get_iface("eth1", crate::InterfaceType::Ethernet)
            .unwrap()
            .clone(),
    );
    let revert = with_vrf.generate_revert(&before_vrf).unwrap();
    assert!(revert.routes.config.as_ref().unwrap()[0].vrf_name.is_none());
    let replay = MergedNetworkState::new(
        revert,
        with_vrf,
        NetworkStateMode::default(),
        false,
    )
    .unwrap();
    assert!(replay.routes.merged.is_empty());
}

#[test]
fn test_unicast_route_metric_reassertion_and_revert_with_a_peer() {
    let current: NetworkState = serde_yaml::from_str(
        r#"
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          ipv4:
            enabled: true
        routes:
          config:
          - destination: 198.51.100.0/24
            next-hop-interface: eth1
            metric: 50
          - destination: 198.51.100.0/24
            next-hop-interface: eth1
            metric: 100
        "#,
    )
    .unwrap();
    let mut desired = current.clone();
    let entries = desired.routes.config.as_mut().unwrap();
    entries.truncate(1);
    entries[0].metric = Some(200);

    let unchanged = MergedNetworkState::new(
        desired.clone(),
        current.clone(),
        NetworkStateMode::default(),
        false,
    )
    .unwrap();
    unchanged
        .routes
        .verify(&current.routes, &[], &current.interfaces)
        .unwrap();
    assert!(desired.gen_diff(&current).unwrap().routes.config.is_none());
    assert!(
        desired
            .generate_revert(&current)
            .unwrap()
            .routes
            .config
            .is_none()
    );

    let entry = &mut desired.routes.config.as_mut().unwrap()[0];
    entry.state = Some(RouteState::Absent);
    entry.metric = Some(50);
    let forward = MergedNetworkState::new(
        desired.clone(),
        current.clone(),
        NetworkStateMode::default(),
        false,
    )
    .unwrap();
    let mut updated = current.clone();
    updated.routes.config = Some(forward.routes.merged["eth1"].clone());
    assert_eq!(updated.routes.config.as_ref().unwrap().len(), 1);
    assert_eq!(updated.routes.config.as_ref().unwrap()[0].metric, Some(100));
    forward
        .routes
        .verify(&updated.routes, &[], &updated.interfaces)
        .unwrap();
    assert!(
        forward
            .routes
            .verify(&current.routes, &[], &current.interfaces)
            .is_err()
    );

    let revert = desired.generate_revert(&current).unwrap();
    let restored = MergedNetworkState::new(
        revert,
        updated,
        NetworkStateMode::default(),
        false,
    )
    .unwrap();
    let routes = &restored.routes.merged["eth1"];
    assert_eq!(routes.len(), 2);
    assert_eq!(routes[0].metric, Some(50));
    assert_eq!(routes[1].metric, Some(100));
    assert_eq!(restored.routes.changed_routes.len(), 1);
    assert!(
        restored
            .routes
            .verify(&restored.routes.current, &[], &current.interfaces)
            .is_err()
    );
    restored
        .routes
        .verify(&current.routes, &[], &current.interfaces)
        .unwrap();
}

#[test]
fn test_gen_revert_limits_auto_priority_rule_removal() {
    let current: NetworkState = serde_yaml::from_str(
        r#"
        route-rules:
          config:
          - ip-from: 192.0.2.10/32
            route-table: 100
            priority: 30000
        "#,
    )
    .unwrap();
    let desired: NetworkState = serde_yaml::from_str(
        r#"
        route-rules:
          config:
          - ip-from: 192.0.2.10/32
        "#,
    )
    .unwrap();

    let revert = desired.generate_revert(&current).unwrap();
    let rules = revert.rules.config.as_ref().unwrap();
    assert_eq!(rules.len(), 1);
    assert!(rules[0].is_absent());
    assert_eq!(rules[0].priority, Some(30001));
    assert_eq!(rules[0].table_id, Some(254));
    assert!(!rules[0].is_match(&current.rules.config.as_ref().unwrap()[0]));
}

#[test]
fn test_gen_revert_preserves_tableless_terminal_rules() {
    let current: NetworkState = serde_yaml::from_str(
        r#"
        route-rules:
          config:
          - family: ipv4
            ip-from: 192.0.2.10/32
            route-table: 254
            priority: 1000
          - family: ipv4
            action: blackhole
            priority: 2000
          - family: ipv4
            action: prohibit
            route-table: 0
            priority: 3000
        "#,
    )
    .unwrap();
    let desired: NetworkState = serde_yaml::from_str(
        r#"
        route-rules:
          config:
          - state: absent
            route-table: 254
        "#,
    )
    .unwrap();

    let diff = desired.gen_diff(&current).unwrap();
    let removed = diff.rules.config.unwrap();
    assert_eq!(removed.len(), 1, "{removed:?}");
    assert_eq!(removed[0].priority, Some(1000));
    assert!(removed[0].is_absent());

    let revert = desired.generate_revert(&current).unwrap();
    let restored = revert.rules.config.unwrap();
    assert_eq!(restored, current.rules.config.unwrap()[..1]);
}
