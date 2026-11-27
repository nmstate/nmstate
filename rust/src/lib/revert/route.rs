// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use crate::{
    MergedRoutes, RouteEntry, RouteState, Routes, route::desired_route_covers,
};

impl MergedRoutes {
    pub(crate) fn generate_revert(&self) -> Routes {
        let mut revert_rts: Vec<RouteEntry> = Vec::new();

        let empty_vec: Vec<RouteEntry> = Vec::new();

        let current_rts = self.current.config.as_ref().unwrap_or(&empty_vec);

        let has_authoritative_scope = self
            .desired
            .authoritative
            .as_ref()
            .is_some_and(|scopes| !scopes.is_empty());

        // Delete routes this transaction added. Pre-existing routes that the
        // desired state still lists are kept, which is required when an
        // authoritative scope replaces a set but retains some of it.
        if let Some(config_rts) = self.desired.config.as_ref() {
            for config_rt in config_rts.iter().filter(|r| !r.is_absent()) {
                let already_present = current_rts.iter().any(|cur_rt| {
                    if has_authoritative_scope {
                        desired_route_covers(config_rt, cur_rt)
                    } else {
                        config_rt.is_match(cur_rt)
                    }
                });
                if !already_present {
                    let mut rt = config_rt.clone();
                    rt.state = Some(RouteState::Absent);
                    revert_rts.push(rt);
                }
            }
        }

        // Add back routes removed during merge (explicit absent entries and
        // inferred special-route replacements tracked in changed_routes).
        // Each removed metric is its own entry. A wildcard absent (no metric)
        // still restores the first current match.
        let mut restored_indexes: HashSet<usize> = HashSet::new();
        for removed_rt in self.changed_routes.iter().filter(|r| r.is_absent()) {
            for (index, cur_rt) in current_rts.iter().enumerate() {
                if restored_indexes.contains(&index) {
                    continue;
                }
                if removed_route_matches_current(removed_rt, cur_rt) {
                    revert_rts.push(cur_rt.clone());
                    restored_indexes.insert(index);
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

fn removed_route_matches_current(
    removed: &RouteEntry,
    current: &RouteEntry,
) -> bool {
    let mut matcher = removed.clone();
    matcher.state = None;
    if !matcher.is_match(current) {
        return false;
    }
    if removed.metric.is_some() {
        removed.effective_metric() == current.effective_metric()
    } else {
        true
    }
}
