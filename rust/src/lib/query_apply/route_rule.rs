// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use crate::{
    ErrorKind, MergedRouteRules, NmstateError, RouteRuleEntry, RouteRules,
};

impl MergedRouteRules {
    pub(crate) fn gen_diff(&self) -> RouteRules {
        if self.desired == self.current {
            return RouteRules::default();
        }

        let mut changed_rules: Vec<RouteRuleEntry> = Vec::new();
        let mut cur_rules: HashSet<&RouteRuleEntry> = HashSet::new();

        if let Some(rules) = self.current.config.as_ref() {
            for rule in rules {
                cur_rules.insert(rule);
            }
        }

        for rule in self.for_apply.as_slice() {
            if rule.is_absent() || !cur_rules.contains(rule) {
                changed_rules.push(rule.clone());
            }
        }

        RouteRules {
            config: if changed_rules.is_empty() {
                None
            } else {
                Some(changed_rules)
            },
        }
    }

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
