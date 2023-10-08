// SPDX-License-Identifier: Apache-2.0

use crate::{MergedRouteRules, RouteRuleEntry, RouteRuleState, RouteRules};

impl MergedRouteRules {
    pub(crate) fn generate_revert(&self) -> RouteRules {
        let mut revert_rules: Vec<RouteRuleEntry> = Vec::new();
        let empty_vec: Vec<RouteRuleEntry> = Vec::new();

        for des_rule in
            self.desired.config.as_ref().unwrap_or(&empty_vec).iter()
        {
            if des_rule.is_absent() {
                for cur_rule in self
                    .current
                    .config
                    .as_ref()
                    .unwrap_or(&empty_vec)
                    .iter()
                    .filter(|r| des_rule.is_match(r))
                {
                    revert_rules.push(cur_rule.clone());
                }
            } else {
                let mut rule = des_rule.clone();
                rule.state = Some(RouteRuleState::Absent);
                revert_rules.push(rule);
            }
        }

        revert_rules.sort_unstable();

        if revert_rules.is_empty() {
            RouteRules::default()
        } else {
            RouteRules {
                config: Some(revert_rules),
                ..Default::default()
            }
        }
    }
}
