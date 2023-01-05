// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, MergedRoutes, NmstateError, RouteEntry, Routes};

impl MergedRoutes {
    fn routes_for_verify(&self) -> Vec<RouteEntry> {
        let mut desired_routes = Vec::new();
        if let Some(rts) = self.desired.config.as_ref() {
            for rt in rts {
                let mut rt = rt.clone();
                rt.sanitize().ok();
                desired_routes.push(rt);
            }
        }
        desired_routes.sort_unstable();
        desired_routes.dedup();

        // Remove the absent route if matching normal route is also desired.
        let mut new_desired_routes = Vec::new();

        for rt in desired_routes.as_slice() {
            if (!rt.is_absent())
                || desired_routes.as_slice().iter().any(|r| rt.is_match(r))
            {
                new_desired_routes.push(rt.clone());
            }
        }

        new_desired_routes
    }

    // Kernel might append additional routes. For example, IPv6 default
    // gateway will generate /128 static direct route.
    // Hence, we only check:
    // * desired absent route is removed unless another matching route been
    //   added.
    // * desired static route exists.
    pub(crate) fn verify(
        &self,
        current: &Routes,
        ignored_ifaces: &[&str],
    ) -> Result<(), NmstateError> {
        let mut cur_routes: Vec<&RouteEntry> = Vec::new();
        if let Some(cur_rts) = current.config.as_ref() {
            for cur_rt in cur_rts {
                if let Some(via) = cur_rt.next_hop_iface.as_ref() {
                    if ignored_ifaces.contains(&via.as_str()) {
                        continue;
                    }
                }
                cur_routes.push(cur_rt);
            }
        }
        cur_routes.dedup();
        let routes_for_verify = self.routes_for_verify();

        for rt in routes_for_verify.as_slice() {
            if rt.is_absent() {
                // We do not valid absent route if desire has a match there.
                // For example, user is changing a gateway.
                if routes_for_verify
                    .as_slice()
                    .iter()
                    .any(|r| !r.is_absent() && rt.is_match(r))
                {
                    continue;
                }
                if let Some(cur_rt) = cur_routes
                    .as_slice()
                    .iter()
                    .find(|cur_rt| rt.is_match(cur_rt))
                {
                    return Err(NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Desired absent route {rt} still found \
                            after apply: {cur_rt}",
                        ),
                    ));
                }
            } else if !cur_routes
                .as_slice()
                .iter()
                .any(|cur_rt| rt.is_match(cur_rt))
            {
                return Err(NmstateError::new(
                    ErrorKind::VerificationError,
                    format!("Desired route {rt} not found after apply"),
                ));
            }
        }

        Ok(())
    }
}
