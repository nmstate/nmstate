// SPDX-License-Identifier: Apache-2.0

use std::path::Path;

use crate::{NetworkPolicy, NetworkState};

const EXAMPLE_FOLDER: &str = "../../../examples/policy";
const CURRENT_YAML_FILENAME: &str = "current.yml";
const POLICY_YAML_FILENAME: &str = "policy.yml";
const EXPECTED_YAML_FILENAME: &str = "expected.yml";

#[test]
fn test_policy_examples() {
    let folded_path = std::fs::canonicalize(
        std::env::current_dir().unwrap().join(EXAMPLE_FOLDER),
    )
    .unwrap();

    for entry in std::fs::read_dir(folded_path).unwrap() {
        let entry = entry.unwrap();
        let path = entry.path();
        println!("Testing {path:?}");
        let current_state = load_state(&path.join(CURRENT_YAML_FILENAME));
        let mut policy = load_policy(&path.join(POLICY_YAML_FILENAME));
        let expected_state = serde_yaml::to_string(&load_state(
            &path.join(EXPECTED_YAML_FILENAME),
        ))
        .unwrap();

        policy.current = Some(current_state);
        let state =
            serde_yaml::to_string(&NetworkState::try_from(policy).unwrap())
                .unwrap();
        println!("Got:\n{}", state);
        println!("Expected:\n{}", expected_state);
        assert_eq!(state, expected_state);
        println!("Pass    {path:?}");
    }
}

fn load_policy(file_path: &Path) -> NetworkPolicy {
    println!("Loading NetworkPolicy from {file_path:?}");
    let fd = std::fs::File::open(file_path).unwrap();
    serde_yaml::from_reader(fd).unwrap()
}

fn load_state(file_path: &Path) -> NetworkState {
    println!("Loading NetworkState from {file_path:?}");
    let fd = std::fs::File::open(file_path).unwrap();
    serde_yaml::from_reader(fd).unwrap()
}
