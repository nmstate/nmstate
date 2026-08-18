// SPDX-License-Identifier: Apache-2.0

use crate::{MergedRoutes, RouteEntry, RouteState, Routes};

impl MergedRoutes {
    pub(crate) fn generate_revert(&self) -> Routes {
        let mut revert_rts: Vec<RouteEntry> = Vec::new();

        let empty_vec: Vec<RouteEntry> = Vec::new();

        let current_rts = self.current.config.as_ref().unwrap_or(&empty_vec);

        // Delete added routes
        if let Some(config_rts) = self.desired.config.as_ref() {
            for config_rt in config_rts.iter().filter(|r| !r.is_absent()) {
                let mut rt = config_rt.clone();
                rt.state = Some(RouteState::Absent);
                revert_rts.push(rt);
            }
        }

        // Add back routes removed during merge (explicit absent entries and
        // inferred special-route replacements tracked in changed_routes).
        for removed_rt in self.changed_routes.iter().filter(|r| r.is_absent()) {
            for cur_rt in current_rts {
                let mut matcher = removed_rt.clone();
                matcher.state = None;
                if matcher.is_match(cur_rt) {
                    revert_rts.push(cur_rt.clone());
                    break;
                }
            }
        }

        revert_rts.sort_unstable();

        if revert_rts.is_empty() {
            Routes::default()
        } else {
            Routes {
                config: Some(revert_rts),
                ..Default::default()
            }
        }
    }
}
