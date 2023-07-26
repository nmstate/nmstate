// SPDX-License-Identifier: Apache-2.0

use std::convert::TryFrom;

use super::super::nm_dbus::NmIpRouteRule;

use crate::{
    ip::is_ipv6_addr, ip::AddressFamily, ErrorKind, InterfaceIpAddr,
    NmstateError, RouteRuleEntry,
};

const AF_INET6: i32 = 10;
const AF_INET: i32 = 2;

pub(crate) fn gen_nm_ip_rules(
    rules: &[RouteRuleEntry],
    is_ipv6: bool,
) -> Result<Vec<NmIpRouteRule>, NmstateError> {
    let mut ret = Vec::new();
    for rule in rules {
        let mut nm_rule = NmIpRouteRule::default();
        nm_rule.family = Some(if is_ipv6 { AF_INET6 } else { AF_INET });
        if let Some(family) = rule.family {
            if is_ipv6 != matches!(family, AddressFamily::IPv6) {
                continue;
            }
        }
        if let Some(addr) = rule.ip_from.as_deref() {
            match (is_ipv6, is_ipv6_addr(addr)) {
                (true, true) | (false, false) => {
                    let ip_addr = InterfaceIpAddr::try_from(addr)?;
                    nm_rule.from_len = Some(ip_addr.prefix_length);
                    nm_rule.from = Some(ip_addr.ip.to_string());
                }
                _ => continue,
            }
        }
        if let Some(addr) = rule.ip_to.as_deref() {
            match (is_ipv6, is_ipv6_addr(addr)) {
                (true, true) | (false, false) => {
                    let ip_addr = InterfaceIpAddr::try_from(addr)?;
                    nm_rule.to_len = Some(ip_addr.prefix_length);
                    nm_rule.to = Some(ip_addr.ip.to_string());
                }
                _ => continue,
            }
        }
        nm_rule.priority = match rule.priority {
            Some(RouteRuleEntry::USE_DEFAULT_PRIORITY) | None => {
                return Err(NmstateError::new(
                    ErrorKind::Bug,
                    format!(
                        "NM route rule got None \
                        or USE_DEFAULT_PRIORITY priority: {nm_rule:?}"
                    ),
                ));
            }
            Some(i) => Some(i as u32),
        };
        nm_rule.table = match rule.table_id {
            Some(RouteRuleEntry::USE_DEFAULT_ROUTE_TABLE) | None => {
                Some(RouteRuleEntry::DEFAULR_ROUTE_TABLE_ID)
            }
            Some(i) => Some(i),
        };

        nm_rule.fw_mark = rule.fwmark;
        nm_rule.fw_mask = rule.fwmask;
        if let Some(iif) = rule.iif.as_ref() {
            nm_rule.iifname = Some(iif.to_string());
        }
        if let Some(action) = rule.action.as_ref() {
            nm_rule.action = Some(u8::from(*action).into());
        }
        if let Some(v) = rule.suppress_prefix_length.as_ref() {
            nm_rule.suppress_prefixlength =
                Some(i32::try_from(*v).map_err(|e| {
                    NmstateError::new(
                        ErrorKind::NotSupportedError,
                        format!(
                            "Specified suppress-prefix-length {v} is \
                            not supported by NetworkManager: {e}"
                        ),
                    )
                })?);
        }

        ret.push(nm_rule);
    }
    Ok(ret)
}
