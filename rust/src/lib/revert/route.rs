// SPDX-License-Identifier: Apache-2.0

use crate::{MergedRoutes, RouteEntry, Routes};

impl MergedRoutes {
    pub(crate) fn generate_revert(&self) -> Routes {
        let mut revert_rts = Vec::new();

        for changed_rt in &self.changed_routes {
            if changed_rt.is_absent() {
                let mut rt = changed_rt.clone();
                rt.metric = Some(rt.effective_metric().into());
                rt.state = None;
                revert_rts.push(rt);
            } else {
                revert_rts.push(changed_rt.as_absent_selector());
            }
        }

        RouteEntry::keep_unicast_metric_peers(
            &mut revert_rts,
            self.merged.values().flatten(),
        );

        // An absent route selector can also match untouched current routes.
        // Keep them in the revert because absent entries are applied first.
        for rt in self.current.config.as_deref().unwrap_or_default() {
            if revert_rts
                .iter()
                .any(|r| r.is_absent() && r.matches_absent(rt))
                && !revert_rts.iter().any(|r| r.cmp_for_merge(rt).is_eq())
            {
                let mut rt = rt.clone();
                rt.metric = Some(rt.effective_metric().into());
                revert_rts.push(rt);
            }
        }

        revert_rts.sort_unstable_by(RouteEntry::cmp_for_merge);
        revert_rts.dedup_by(|a, b| a.cmp_for_merge(b).is_eq());

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
