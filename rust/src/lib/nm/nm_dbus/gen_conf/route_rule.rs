// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use super::super::NmIpRouteRule;

const DEFAULT_ROUTE_TABLE: u32 = 254;

impl NmIpRouteRule {
    pub(crate) fn to_keyfile(&self) -> HashMap<String, String> {
        let mut ret = HashMap::new();
        if let Some(priority) = self.priority.as_ref() {
            let mut keys = Vec::new();
            let prio_str = format!("priority {}", priority);
            keys.push(prio_str);

            let to_str = match (self.to.as_ref(), self.to_len.as_ref()) {
                (Some(t), Some(t_len)) => format!("to {}/{}", t, t_len),
                (Some(t), None) => format!("to {}", t),
                _ => "".to_string(),
            };
            if !to_str.is_empty() {
                keys.push(to_str);
            }

            let from_str = match (self.from.as_ref(), self.from_len.as_ref()) {
                (Some(f), Some(f_len)) => format!("from {}/{}", f, f_len),
                (Some(f), None) => format!("from {}", f),
                _ => "".to_string(),
            };
            if !from_str.is_empty() {
                keys.push(from_str);
            }

            let mut table_str = format!("table {}", DEFAULT_ROUTE_TABLE);
            if let Some(table) = self.table {
                table_str = format!("table {}", table);
            }
            keys.push(table_str);

            let fwmark_line = match (self.fw_mark, self.fw_mask) {
                (Some(mark), Some(mask)) => format!("fwmark {}/{}", mark, mask),
                (Some(mark), None) => format!("fwmark {}", mark),
                _ => "".to_string(),
            };
            if !fwmark_line.is_empty() {
                keys.push(fwmark_line);
            }

            let rl_line = keys.join(" ");
            ret.insert("".to_string(), rl_line);
        }
        ret
    }
}
