// SPDX-License-Identifier: Apache-2.0

use crate::NmstateError;

const NEXT_TOKEN_START_CHARS: [char; 6] = [' ', '=', '!', '|', '"', ':'];

#[derive(Clone, Eq, PartialEq, Debug)]
pub(crate) enum NetworkCaptureToken {
    Path(Vec<String>, usize), // Example: routes.running.destination
    Value(String, usize),     // Example: 13 or "Abc"
    Pipe(usize),              // |
    Replace(usize),           // :=
    Equal(usize),             // ==
    Null(usize),              // Unquoted null or NULL or Null
}

impl Default for NetworkCaptureToken {
    fn default() -> Self {
        Self::Value(String::new(), 0)
    }
}

impl NetworkCaptureToken {
    pub(crate) fn pos(&self) -> usize {
        match self {
            Self::Path(_, p)
            | Self::Value(_, p)
            | Self::Pipe(p)
            | Self::Replace(p)
            | Self::Equal(p)
            | Self::Null(p) => *p,
        }
    }
}

pub(crate) fn parse_str_to_capture_tokens(
    line: &str,
) -> Result<Vec<NetworkCaptureToken>, NmstateError> {
    let mut ret: Vec<NetworkCaptureToken> = Vec::new();
    let line_chars: Vec<char> = line.chars().collect();
    let mut line_iter = line.char_indices().peekable();

    while let Some((pos, c)) = line_iter.next() {
        log::debug!(
            "Token processing {:?}, got {:?}, cur: {}",
            String::from_iter(&line_chars[pos..]),
            ret,
            c
        );
        match c {
            '=' => {
                if let Some((_, c)) = line_iter.next() {
                    if c == '=' {
                        if ret.as_slice().iter().any(|c| {
                            matches!(c, &NetworkCaptureToken::Equal(_))
                        }) {
                            return Err(NmstateError::new_policy_error(
                                "Nmpolicy does not allows two equal action"
                                    .to_string(),
                                line,
                                pos,
                            ));
                        }
                        ret.push(NetworkCaptureToken::Equal(pos));
                    } else {
                        return Err(NmstateError::new_policy_error(
                            "Invalid equal action string after =, \
                            expecting another '='"
                                .to_string(),
                            line,
                            pos + 1,
                        ));
                    }
                } else {
                    return Err(NmstateError::new_policy_error(
                        "Invalid equal action string after =, \
                        expecting another '=', but got nothing"
                            .to_string(),
                        line,
                        pos,
                    ));
                }
            }
            '|' => {
                if ret
                    .as_slice()
                    .iter()
                    .any(|t| matches!(t, &NetworkCaptureToken::Pipe(_)))
                {
                    return Err(NmstateError::new_policy_error(
                        "Nmpolicy does not allows two pipe action".to_string(),
                        line,
                        pos,
                    ));
                } else {
                    ret.push(NetworkCaptureToken::Pipe(pos));
                }
            }
            ':' => {
                if let Some((_, c)) = line_iter.next() {
                    if c == '=' {
                        if ret.as_slice().iter().any(|t| {
                            matches!(t, &NetworkCaptureToken::Replace(_))
                        }) {
                            return Err(NmstateError::new_policy_error(
                                "Nmpolicy does not allows two replace action"
                                    .to_string(),
                                line,
                                pos,
                            ));
                        } else {
                            ret.push(NetworkCaptureToken::Replace(pos));
                        }
                    } else {
                        return Err(NmstateError::new_policy_error(
                            "Invalid replace action string after =, \
                            expecting another '='"
                                .to_string(),
                            line,
                            pos + 1,
                        ));
                    }
                } else {
                    return Err(NmstateError::new_policy_error(
                        "Invalid replace action string after =, \
                        expecting another '=', but got nothing"
                            .to_string(),
                        line,
                        pos,
                    ));
                }
            }
            '"' => {
                // Continue till next double quote
                if pos + 1 >= line_chars.len()
                    || !&line_chars[pos + 1..].contains(&'"')
                {
                    return Err(NmstateError::new_policy_error(
                        "No ending double quote".to_string(),
                        line,
                        pos,
                    ));
                }
                let mut quoted_string_chars = Vec::new();
                for (_, c) in line_iter.by_ref() {
                    if c != '"' {
                        quoted_string_chars.push(c);
                    } else {
                        break;
                    }
                }
                if !quoted_string_chars.is_empty() {
                    ret.push(NetworkCaptureToken::Value(
                        String::from_iter(quoted_string_chars.as_slice()),
                        pos + 1,
                    ));
                }
            }
            _ => {
                if c.is_whitespace() {
                    continue;
                }
                let block = consume_till_next_token(c, &mut line_iter);
                if block.contains('.') {
                    ret.push(NetworkCaptureToken::Path(
                        block.split('.').map(|c| c.to_string()).collect(),
                        pos,
                    ));
                } else if !block.is_empty() {
                    if block.to_lowercase() == "null" {
                        ret.push(NetworkCaptureToken::Null(pos));
                    } else {
                        ret.push(NetworkCaptureToken::Value(block, pos));
                    }
                }
            }
        }
    }

    if let Some(pos) = ret
        .as_slice()
        .iter()
        .position(|c| matches!(c, &NetworkCaptureToken::Pipe(_)))
    {
        if ret.len() == pos + 1 {
            return Err(NmstateError::new_policy_error(
                "Invalid pipe action: no property path defined".to_string(),
                line,
                ret[pos].pos(),
            ));
        }
        if !matches!(&ret[pos + 1], &NetworkCaptureToken::Path(_, _)) {
            return Err(NmstateError::new_policy_error(
                "Invalid pipe action: only property path allowed after pipe"
                    .to_string(),
                line,
                ret[pos + 1].pos(),
            ));
        }
    }

    Ok(ret)
}

fn consume_till_next_token(
    leading_char: char,
    line_iter: &mut std::iter::Peekable<std::str::CharIndices>,
) -> String {
    let mut block = vec![leading_char];
    while let Some((_, c)) = line_iter.peek() {
        if NEXT_TOKEN_START_CHARS.contains(c) {
            break;
        } else if let Some((_, c)) = line_iter.next() {
            block.push(c);
        } else {
            break;
        }
    }
    String::from_iter(block.as_slice()).trim().to_string()
}

#[derive(Clone, Eq, PartialEq, Debug)]
pub(crate) enum NetworkTemplateToken {
    Value(String, usize),
    ReferenceStart(usize),    // {{
    Path(Vec<String>, usize), // Example: routes.running.destination
    ReferenceEnd(usize),      // }}
}

impl NetworkTemplateToken {
    pub(crate) fn pos(&self) -> usize {
        match self {
            Self::Path(_, p)
            | Self::Value(_, p)
            | Self::ReferenceStart(p)
            | Self::ReferenceEnd(p) => *p,
        }
    }
}

pub(crate) fn parse_str_to_template_tokens(
    line: &str,
) -> Result<Vec<NetworkTemplateToken>, NmstateError> {
    let mut ret: Vec<NetworkTemplateToken> = Vec::new();
    let line_chars: Vec<char> = line.chars().collect();
    let mut line_iter = line.char_indices().peekable();

    while let Some((pos, c)) = line_iter.next() {
        log::debug!(
            "Token processing {:?}, got {:?}, cur: {}",
            String::from_iter(&line_chars[pos..]),
            ret,
            c
        );
        match c {
            '{' => {
                if let Some((_, c)) = line_iter.next() {
                    if c == '{' {
                        if ret.as_slice().iter().any(|c| {
                            matches!(
                                c,
                                &NetworkTemplateToken::ReferenceStart(_)
                            )
                        }) {
                            return Err(NmstateError::new_policy_error(
                                "Nmpolicy does not allow multiple references \
                                {{}}"
                                    .to_string(),
                                line,
                                pos,
                            ));
                        }
                        ret.push(NetworkTemplateToken::ReferenceStart(pos));
                        // Normally we have a white space after '}', let's
                        // remove it and move on the pos
                        while let Some((_, c)) = line_iter.peek() {
                            if c.is_whitespace() {
                                line_iter.next();
                            } else {
                                break;
                            }
                        }
                    } else {
                        return Err(NmstateError::new_policy_error(
                            "Invalid reference action string after {, \
                            expecting another '{'"
                                .to_string(),
                            line,
                            pos,
                        ));
                    }
                } else {
                    return Err(NmstateError::new_policy_error(
                        "Invalid reference action string after =, \
                        expecting another '{', but got nothing"
                            .to_string(),
                        line,
                        pos,
                    ));
                }
            }
            '}' => {
                if let Some((_, c)) = line_iter.next() {
                    if c == '}' {
                        if ret.as_slice().iter().any(|c| {
                            matches!(c, &NetworkTemplateToken::ReferenceEnd(_))
                        }) {
                            return Err(NmstateError::new_policy_error(
                                "Nmpolicy does not allow multiple references \
                                {{}}"
                                    .to_string(),
                                line,
                                pos,
                            ));
                        }
                        ret.push(NetworkTemplateToken::ReferenceEnd(pos));
                    } else {
                        return Err(NmstateError::new_policy_error(
                            "Invalid reference action string after }, \
                            expecting another '}'"
                                .to_string(),
                            line,
                            pos,
                        ));
                    }
                } else {
                    return Err(NmstateError::new_policy_error(
                        "Invalid reference action string after }, \
                        expecting another '}', but got nothing"
                            .to_string(),
                        line,
                        pos,
                    ));
                }
            }
            _ => {
                let mut chars = vec![c];
                while let Some((_, c)) = line_iter.peek() {
                    if ['{', '}'].contains(c) {
                        break;
                    } else if let Some((_, c)) = line_iter.next() {
                        if c.is_whitespace() {
                            break;
                        }
                        chars.push(c);
                    } else {
                        break;
                    }
                }
                // position should be first char after trimmed
                let subline =
                    String::from_iter(chars.as_slice()).trim().to_string();
                if subline.is_empty() {
                    continue;
                }
                if subline.contains('.') && !subline.starts_with('.') {
                    ret.push(NetworkTemplateToken::Path(
                        subline.split('.').map(|c| c.to_string()).collect(),
                        pos,
                    ));
                } else {
                    ret.push(NetworkTemplateToken::Value(subline, pos));
                }
            }
        }
    }

    // The reference start and end should be paired.
    if let Some(token_start) = ret
        .as_slice()
        .iter()
        .find(|c| matches!(c, &NetworkTemplateToken::ReferenceStart(_)))
    {
        if !ret
            .as_slice()
            .iter()
            .any(|c| matches!(c, &NetworkTemplateToken::ReferenceEnd(_)))
        {
            return Err(NmstateError::new_policy_error(
                "No reference end }} found".to_string(),
                line,
                token_start.pos(),
            ));
        }
    }

    if let Some(token_end) = ret
        .as_slice()
        .iter()
        .find(|c| matches!(c, &NetworkTemplateToken::ReferenceEnd(_)))
    {
        if !ret
            .as_slice()
            .iter()
            .any(|c| matches!(c, &NetworkTemplateToken::ReferenceStart(_)))
        {
            return Err(NmstateError::new_policy_error(
                "No reference start {{ found".to_string(),
                line,
                token_end.pos(),
            ));
        }
    }

    if let (Some(token_start_pos), Some(token_end_pos)) = (
        ret.as_slice().iter().position(|t| {
            matches!(t, &NetworkTemplateToken::ReferenceStart(_))
        }),
        ret.as_slice()
            .iter()
            .position(|t| matches!(t, &NetworkTemplateToken::ReferenceEnd(_))),
    ) {
        if token_start_pos >= token_end_pos {
            return Err(NmstateError::new_policy_error(
                "The reference start {{ can not be placed before \
                reference end }}"
                    .to_string(),
                line,
                ret[token_end_pos].pos(),
            ));
        }
        if token_start_pos + 1 >= token_end_pos {
            return Err(NmstateError::new_policy_error(
                "No property path between reference start {{ and \
                reference end }}"
                    .to_string(),
                line,
                ret[token_end_pos].pos() - 1,
            ));
        }
        if token_start_pos + 2 != token_end_pos {
            return Err(NmstateError::new_policy_error(
                "Only allows single property path between reference \
                start {{ and reference end }}"
                    .to_string(),
                line,
                ret[token_start_pos + 2].pos(),
            ));
        }
    }

    Ok(ret)
}
