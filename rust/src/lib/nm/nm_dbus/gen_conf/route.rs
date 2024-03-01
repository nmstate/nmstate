// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::fmt::Write;

use super::super::NmIpRoute;

const DEFAULT_ROUTE_TABLE: u32 = 254;

impl NmIpRoute {
    pub(crate) fn to_keyfile(&self) -> HashMap<String, String> {
        let mut ret = HashMap::new();
        if let (Some(dest), Some(prefix)) =
            (self.dest.as_ref(), self.prefix.as_ref())
        {
            let dest = format!("{dest}/{prefix}");
            let rt_line = match (self.next_hop.as_ref(), self.metric.as_ref()) {
                (Some(n), Some(m)) => vec![dest, n.to_string(), m.to_string()],
                (Some(n), None) => vec![dest, n.to_string()],
                (None, Some(m)) => vec![dest, "".to_string(), m.to_string()],
                (None, None) => vec![dest],
            };
            ret.insert("".to_string(), rt_line.join(","));
            let mut opt_string =
                format!("table={}", self.table.unwrap_or(DEFAULT_ROUTE_TABLE));
            if let Some(weight) = self.weight {
                write!(opt_string, ",weight={}", weight).ok();
            }
            if let Some(route_type) = self.route_type.as_ref() {
                write!(opt_string, ",type={}", route_type).ok();
            }
            if let Some(cwnd) = self.cwnd {
                write!(opt_string, ",cwnd={}", cwnd).ok();
            }
            ret.insert("options".to_string(), opt_string);
        }
        ret
    }
}
