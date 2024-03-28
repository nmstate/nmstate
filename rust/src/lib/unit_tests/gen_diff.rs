// SPDX-License-Identifier: Apache-2.0

use crate::NetworkState;

const TEST_DATA_FOLDER_PATH: &str = "unit_tests/gen_diff_test_files";
const DESIRED_FILE_NAME: &str = "desired.yml";
const CURRENT_FILE_NAME: &str = "current.yml";
const REVERT_FILE_NAME: &str = "diff.yml";

#[test]
fn test_gen_diff() {
    let folded_path =
        std::path::Path::new(&std::env::var("CARGO_MANIFEST_DIR").unwrap())
            .join(TEST_DATA_FOLDER_PATH);

    for entry in std::fs::read_dir(folded_path).unwrap() {
        let entry = entry.unwrap();
        let path = entry.path();
        let current = load_state(&path.join(CURRENT_FILE_NAME));
        let desired = load_state(&path.join(DESIRED_FILE_NAME));
        let expected_diff =
            serde_yaml::to_string(&load_state(&path.join(REVERT_FILE_NAME)))
                .unwrap();
        let diff = serde_yaml::to_string(&desired.gen_diff(&current).unwrap())
            .unwrap();
        if expected_diff != diff {
            panic!(
                "FAIL: {:?}\nExpected:\n\n{}\nGot:\n\n{}",
                entry.file_name(),
                expected_diff,
                diff
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
            panic!("FAIL to load NetworkState from {:?}: {}", file_path, e);
        }
    }
}
