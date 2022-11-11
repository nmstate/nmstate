// SPDX-License-Identifier: Apache-2.0

use crate::{ErrorKind, NmstateError, Routes};

impl Routes {
    // Kernel might append additional routes. For example, IPv6 default
    // gateway will generate /128 static direct route.
    // Hence, we only check:
    // * desired absent route is removed unless another matching route been
    //   added.
    // * desired static route exists.
    pub(crate) fn verify(
        &self,
        current: &Self,
        ignored_ifaces: &[String],
    ) -> Result<(), NmstateError> {
        if let Some(mut config_routes) = self.config.clone() {
            config_routes.sort_unstable();
            config_routes.dedup();
            for r in config_routes.iter_mut() {
                r.sanitize().ok();
            }
            let cur_config_routes = match current.config.as_ref() {
                Some(c) => {
                    let mut routes = c.to_vec();
                    routes.sort_unstable();
                    routes.dedup();
                    routes
                }
                None => Vec::new(),
            };
            for desire_route in config_routes.iter().filter(|r| !r.is_absent())
            {
                if !cur_config_routes.iter().any(|r| desire_route.is_match(r)) {
                    let e = NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Desired route {:?} not found after apply",
                            desire_route
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }

            for absent_route in config_routes.iter().filter(|r| r.is_absent()) {
                // We ignore absent route if user is replacing old route
                // with new one.
                if config_routes
                    .iter()
                    .any(|r| (!r.is_absent()) && absent_route.is_match(r))
                {
                    continue;
                }

                if let Some(cur_route) =
                    cur_config_routes.iter().find(|r|
                        if let Some(iface) = r.next_hop_iface.as_ref() {
                            !ignored_ifaces.contains(
                                iface
                            )
                        } else {
                            true
                        } && absent_route.is_match(r))
                {
                    let e = NmstateError::new(
                        ErrorKind::VerificationError,
                        format!(
                            "Desired absent route {:?} still found \
                            after apply: {:?}",
                            absent_route, cur_route
                        ),
                    );
                    log::error!("{}", e);
                    return Err(e);
                }
            }
        }
        Ok(())
    }

    pub(crate) fn remove_ignored_iface_routes(
        &mut self,
        iface_names: &[String],
    ) {
        if let Some(config_routes) = self.config.as_mut() {
            config_routes.retain(|r| {
                if let Some(i) = r.next_hop_iface.as_ref() {
                    !iface_names.contains(i)
                } else {
                    true
                }
            })
        }
    }
}
