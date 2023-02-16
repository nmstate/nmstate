// SPDX-License-Identifier: Apache-2.0

use crate::{
    ErrorKind, MergedRouteRules, NmstateError, RouteRuleEntry, RouteRules,
};

impl MergedRouteRules {
    pub(crate) fn verify(
        &self,
        current: &RouteRules,
        ignored_ifaces: &[&str],
    ) -> Result<(), NmstateError> {
        let mut cur_rules: Vec<&RouteRuleEntry> = Vec::new();
        if let Some(rules) = current.config.as_ref() {
            for cur_rule in rules {
                if let Some(iif) = cur_rule.iif.as_ref() {
                    if ignored_ifaces.contains(&iif.as_str()) {
                        continue;
                    }
                }
                cur_rules.push(cur_rule);
            }
        }
        for rule in self.for_verify.as_slice() {
            if rule.is_absent() {
                // Ignore absent rule when desired matches
                if self
                    .for_verify
                    .as_slice()
                    .iter()
                    .any(|r| !r.is_absent() && rule.is_match(r))
                {
                    continue;
                }
                if let Some(cur_rt) = cur_rules
                    .as_slice()
                    .iter()
                    .find(|cur_r| rule.is_match(cur_r))
                {
                    return Err(NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Desired absent route rule {rule} still found \
                            after apply: {cur_rt}"
                        ),
                    ));
                }
            } else if !cur_rules
                .as_slice()
                .iter()
                .any(|cur_r| rule.is_match(cur_r))
            {
                return Err(NmstateError::new(
                    ErrorKind::VerificationError,
                    format!("Desired route rule {rule} not found after apply"),
                ));
            }
        }
        Ok(())
    }
}
