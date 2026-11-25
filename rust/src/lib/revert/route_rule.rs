// SPDX-License-Identifier: Apache-2.0

use crate::{MergedRouteRules, NmstateError, RouteRuleState, RouteRules};

impl MergedRouteRules {
    pub(crate) fn generate_revert(&self) -> Result<RouteRules, NmstateError> {
        let current_rules = self.current.config.as_deref().unwrap_or_default();
        let mut normalized_current = current_rules.to_vec();
        for rule in &mut normalized_current {
            rule.sanitize()?;
        }

        let present_rules: Vec<_> =
            self.for_apply.iter().filter(|r| !r.is_absent()).collect();
        let mut revert_rules = Vec::new();

        for rule in &present_rules {
            if !normalized_current.iter().any(|r| rule.has_same_config(r)) {
                let mut absent = (*rule).clone();
                absent.state = Some(RouteRuleState::Absent);
                absent.table_id = Some(absent.effective_table_id());
                revert_rules.push(absent);
            }
        }

        for (current, normalized) in
            current_rules.iter().zip(&normalized_current)
        {
            let removed = self
                .for_apply
                .iter()
                .any(|r| r.is_absent() && r.is_match(normalized))
                && !present_rules.iter().any(|r| r.has_same_config(normalized));
            // An absent rule selector can also match an untouched rule with
            // the same priority. Re-add it after the removal.
            if removed
                || revert_rules
                    .iter()
                    .any(|r| r.is_absent() && r.is_match(normalized))
            {
                revert_rules.push(current.clone());
            }
        }

        revert_rules.sort_unstable();

        Ok(RouteRules {
            config: (!revert_rules.is_empty()).then_some(revert_rules),
        })
    }
}
