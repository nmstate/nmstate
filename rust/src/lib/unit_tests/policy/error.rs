// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::{
    policy::{
        capture::NetworkCaptureCommand, token::parse_str_to_template_tokens,
    },
    ErrorKind, NetworkState, NetworkStateTemplate,
};

#[test]
fn test_policy_invalid_equal_action_not_two_equal() {
    let line = r#"routes.running.next-hop-interface=!"br1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(
            e.position(),
            "routes.running.next-hop-interface=!".len() - 1
        );
    }
}

#[test]
fn test_policy_single_equal_at_end() {
    let line = "routes.running.next-hop-interface=";
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(
            e.position(),
            "routes.running.next-hop-interface=".len() - 1
        );
    }
}

#[test]
fn test_policy_invalid_replace_action_no_equal_after() {
    let line = r#"routes.running.next-hop-interface::"br1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(
            e.position(),
            "routes.running.next-hop-interface::".len() - 1
        );
    }
}

#[test]
fn test_policy_single_colon_at_end() {
    let line = "routes.running.next-hop-interface:";
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(
            e.position(),
            "routes.running.next-hop-interface:".len() - 1
        );
    }
}

#[test]
fn test_policy_no_ending_quote() {
    let line = r#"routes.running.next-hop-interface=="br1"""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(
            e.position(),
            "routes.running.next-hop-interface==\"br1\"\"".len() - 1
        );
    }
}

#[test]
fn test_policy_two_pipes() {
    let line = r#"capture.abc | capture.abc | interface.name="eth1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "capture.abc | capture.abc |".len() - 1);
    }
}

#[test]
fn test_policy_two_replaces() {
    let line = r#"capture.abc | capture.abc := interface.name := "eth1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(
            e.position(),
            "capture.abc | capture.abc := interface.name :".len() - 1
        );
    }
}

#[test]
fn test_policy_two_equals() {
    let line = r#"capture.abc | capture.abc == interface.name == "eth1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(
            e.position(),
            "capture.abc | capture.abc == interface.name =".len() - 1
        );
    }
}

#[test]
fn test_policy_pipe_not_started_with_capture() {
    let line = r#"kapture.abc | interface.name == "eth1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), 0);
    }
}

#[test]
fn test_policy_pipe_invalid_capture_two_capture_name() {
    let line = r#"capture.abc.abd | interface.name == "eth1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), 0);
    }
}

#[test]
fn test_policy_pipe_invalid_capture_no_capture() {
    let line = r#"interfaces | interface.name == "eth1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), 0);
    }
}

#[test]
fn test_policy_equal_got_no_value_defined() {
    let line = "interface.name ==";
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "interface.name =".len() - 1);
    }
}

#[test]
fn test_policy_equal_got_2_values() {
    let line = r#"interface.name == "eth1" interface.name"#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        println!("HAHA {e}");
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "interface.name == \"e".len() - 1);
    }
}

#[test]
fn test_policy_equal_capture_no_path_afterwards() {
    let line = r#"capture.abc == "eth1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), 0);
    }
}

#[test]
fn test_policy_equal_capture_no_name_afterwards() {
    let line = r#"capture == "eth1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), 0);
    }
}

#[test]
fn test_policy_replace_got_no_value_defined() {
    let line = "interface.name :=";
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "interface.name :".len() - 1);
    }
}

#[test]
fn test_policy_replace_got_2_value() {
    let line = r#"interface.name := "eth1" interface.name"#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "interface.name := \"e".len() - 1);
    }
}

#[test]
fn test_policy_replace_capture_no_path_afterwards() {
    let line = r#"capture.abc := "eth1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), 0);
    }
}

#[test]
fn test_policy_replace_capture_no_name_afterwards() {
    let line = r#"capture := "eth1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), 0);
    }
}

#[test]
fn test_policy_capture_not_found() {
    let line = r#"capture.void.interface.name == "eth1""#;
    let cmd = NetworkCaptureCommand::parse(line).unwrap();
    let result = cmd.execute(&NetworkState::new(), &HashMap::new());
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "capture.v".len() - 1);
    }
}

#[test]
fn test_policy_reference_no_ending() {
    let line = "{{ capture.void.interface.0.name";
    let result = parse_str_to_template_tokens(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), 0);
    }
}

#[test]
fn test_policy_reference_no_start() {
    let line = "capture.void.interface.0.name }}";
    let result = parse_str_to_template_tokens(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "capture.void.interface.0.name }".len() - 1);
    }
}

#[test]
fn test_policy_reference_end_before_start() {
    let line = "}} capture.void.interface.0.name {{";
    let result = parse_str_to_template_tokens(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), 0)
    }
}

#[test]
fn test_policy_two_references() {
    let line = "{{ {{ capture.void.interface.0.name }} }}";
    let result = parse_str_to_template_tokens(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "{{ {".len() - 1)
    }
}

#[test]
fn test_policy_empty_reference() {
    let line = "{{ }}";
    let result = parse_str_to_template_tokens(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "{{ ".len() - 1)
    }
}

#[test]
fn test_policy_reference_with_two_paths() {
    let line = "{{ capture.void.interface.0.name \
        capture.void.interface.1.name }}";
    let result = parse_str_to_template_tokens(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "{{ capture.void.interface.0.name c".len() - 1)
    }
}

#[test]
fn test_policy_reference_capture_not_found() {
    let template: NetworkStateTemplate = serde_yaml::from_str(
        r#"---
interfaces:
  - name: "{{ capture.void.interface.0.name }}""#,
    )
    .unwrap();
    let capture_results = HashMap::new();
    let result = template.fill_with_captured_data(&capture_results);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), "{{ capture.void.interface.0.name }}");
        assert_eq!(e.position(), "{{ capture.v".len() - 1)
    }
}

#[test]
fn test_policy_reference_capture_concatenate_with_prefix() {
    let template: NetworkStateTemplate = serde_yaml::from_str(
        r#"---
        interfaces:
          - name: "{{ capture.void.interfaces.0.name }}.1""#,
    )
    .unwrap();
    let mut capture_results: HashMap<String, NetworkState> = HashMap::new();
    capture_results.insert(
        "void".to_string(),
        serde_yaml::from_str(
            r#"
            interfaces:
              - name: eth1"#,
        )
        .unwrap(),
    );
    let state = template.fill_with_captured_data(&capture_results).unwrap();
    let ifaces = state.interfaces.to_vec();
    assert_eq!(ifaces.len(), 1);
    assert_eq!(ifaces[0].base_iface().name, "eth1.1");
}

#[test]
fn test_policy_reference_capture_property_not_found() {
    let template: NetworkStateTemplate = serde_yaml::from_str(
        r#"---
        interfaces:
          - name: "{{ capture.void.interface.0.name }}""#,
    )
    .unwrap();
    let mut capture_results: HashMap<String, NetworkState> = HashMap::new();
    capture_results.insert(
        "void".to_string(),
        serde_yaml::from_str(
            r#"
            interfaces:
              - name: eth1"#,
        )
        .unwrap(),
    );
    let result = template.fill_with_captured_data(&capture_results);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), "{{ capture.void.interface.0.name }}");
        assert_eq!(e.position(), "{{ capture.void.i".len() - 1)
    }
}

#[test]
fn test_policy_reference_capture_property_not_array() {
    let template: NetworkStateTemplate = serde_yaml::from_str(
        r#"---
        interfaces:
          - name: "{{ capture.void.0.name }}""#,
    )
    .unwrap();
    let mut capture_results: HashMap<String, NetworkState> = HashMap::new();
    capture_results.insert(
        "void".to_string(),
        serde_yaml::from_str(
            r#"
            interfaces:
              - name: eth1"#,
        )
        .unwrap(),
    );
    let result = template.fill_with_captured_data(&capture_results);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), "{{ capture.void.0.name }}");
        assert_eq!(e.position(), "{{ capture.void.0".len() - 1)
    }
}

#[test]
fn test_policy_ilegal_char() {
    let line = r#"capture.abc | interface.name==-"eth1""#;
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        println!("HAHA {e}");
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "capture.abc | interface.name==-".len() - 1);
    }
}

#[test]
fn test_policy_pipe_at_end() {
    let line = "capture.abc |";
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "capture.abc |".len() - 1);
    }
}

#[test]
fn test_policy_value_after_pipe() {
    let line = "capture.abc | \"eth1\"";
    let result = NetworkCaptureCommand::parse(line);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), line);
        assert_eq!(e.position(), "capture.abc | \"e".len() - 1);
    }
}

#[test]
fn test_policy_template_no_capture() {
    let template: NetworkStateTemplate = serde_yaml::from_str(
        r#"---
interfaces:
  - name: "{{ interface.0.name }}""#,
    )
    .unwrap();
    let capture_results = HashMap::new();
    let result = template.fill_with_captured_data(&capture_results);
    assert!(result.is_err());
    if let Err(e) = result {
        assert_eq!(e.kind(), ErrorKind::PolicyError);
        assert_eq!(e.line(), "{{ interface.0.name }}");
        assert_eq!(e.position(), "{{ i".len() - 1)
    }
}
