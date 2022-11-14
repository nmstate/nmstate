// SPDX-License-Identifier: Apache-2.0

use crate::policy::token::{parse_str_to_capture_tokens, NetworkCaptureToken};

#[test]
fn test_policy_token_quoted_string() {
    assert_eq!(
        parse_str_to_capture_tokens(r#""quoted string""#).unwrap(),
        vec![NetworkCaptureToken::Value("quoted string".into(), 1)]
    )
}

#[test]
fn test_policy_token_equal_number() {
    assert_eq!(
        parse_str_to_capture_tokens("interfaces.mtu==1280").unwrap(),
        vec![
            NetworkCaptureToken::Path(
                vec!["interfaces".into(), "mtu".into()],
                0
            ),
            NetworkCaptureToken::Equal("interfaces.mtu=".len() - 1),
            NetworkCaptureToken::Value(
                "1280".into(),
                "interfaces.mtu==1".len() - 1
            )
        ]
    )
}

#[test]
fn test_policy_token_path_equal_double_quoted_string() {
    assert_eq!(
        parse_str_to_capture_tokens(r#"interfaces.name=="eth1""#).unwrap(),
        vec![
            NetworkCaptureToken::Path(
                vec!["interfaces".into(), "name".into()],
                0
            ),
            NetworkCaptureToken::Equal("interfaces.name=".len() - 1),
            NetworkCaptureToken::Value(
                "eth1".into(),
                "interfaces.name==\"e".len() - 1,
            )
        ]
    )
}

#[test]
fn test_policy_token_path_equal_unquoted_string() {
    assert_eq!(
        parse_str_to_capture_tokens("interfaces.name==eth1").unwrap(),
        vec![
            NetworkCaptureToken::Path(
                vec!["interfaces".into(), "name".into()],
                0
            ),
            NetworkCaptureToken::Equal("interfaces.name=".len() - 1),
            NetworkCaptureToken::Value(
                "eth1".into(),
                "interfaces.name==e".len() - 1
            )
        ]
    )
}

#[test]
fn test_policy_token_path_equal_path() {
    assert_eq!(
        parse_str_to_capture_tokens(
            "interfaces.name==\
                capture.default-gw.routes.running.0.next-hop-interface"
        )
        .unwrap(),
        vec![
            NetworkCaptureToken::Path(
                vec!["interfaces".into(), "name".into(),],
                0
            ),
            NetworkCaptureToken::Equal("interfaces.name=".len() - 1),
            NetworkCaptureToken::Path(
                vec![
                    "capture".into(),
                    "default-gw".into(),
                    "routes".into(),
                    "running".into(),
                    "0".into(),
                    "next-hop-interface".into(),
                ],
                "interfaces.name==c".len() - 1
            )
        ]
    )
}

#[test]
fn test_policy_token_path_pipe() {
    assert_eq!(
        parse_str_to_capture_tokens(
            r#"capture.base-iface-routes | running.a := "br1""#
        )
        .unwrap(),
        vec![
            NetworkCaptureToken::Path(
                vec!["capture".into(), "base-iface-routes".into(),],
                0,
            ),
            NetworkCaptureToken::Pipe("capture.base-iface-routes |".len() - 1),
            NetworkCaptureToken::Path(
                vec!["running".into(), "a".into()],
                "capture.base-iface-routes | r".len() - 1
            ),
            NetworkCaptureToken::Replace(
                "capture.base-iface-routes | running.a :".len() - 1
            ),
            NetworkCaptureToken::Value(
                "br1".into(),
                "capture.base-iface-routes | running.a := \"b".len() - 1
            ),
        ]
    )
}
