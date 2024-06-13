// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use crate::{
    ErrorKind, InterfaceType, Interfaces, MergedRoutes, NmstateError,
    RouteEntry, Routes,
};

impl MergedRoutes {
    pub(crate) fn gen_diff(&self) -> Routes {
        let mut changed_routes: Vec<RouteEntry> = Vec::new();
        let mut current_routes: HashSet<&RouteEntry> = HashSet::new();

        if let Some(rts) = self.current.config.as_ref() {
            for rt in rts {
                current_routes.insert(rt);
            }
        }

        for rts in self.merged.values() {
            for rt in rts {
                if rt.is_absent() || !current_routes.contains(rt) {
                    changed_routes.push(rt.clone());
                }
            }
        }

        Routes {
            config: if !changed_routes.is_empty() {
                Some(changed_routes)
            } else {
                None
            },
            ..Default::default()
        }
    }

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
        current_ifaces: &Interfaces,
    ) -> Result<(), NmstateError> {
        let mut cur_routes: Vec<&RouteEntry> = Vec::new();
        if let Some(cur_rts) = current.config.as_ref() {
            for cur_rt in cur_rts {
                if let Some(via) = cur_rt.next_hop_iface.as_ref() {
                    if ignored_ifaces.contains(&via.as_str())
                        && cur_rt.route_type.is_none()
                    {
                        continue;
                    }
                }
                cur_routes.push(cur_rt);
            }
        }
        cur_routes.dedup();
        let routes_for_verify = self.routes_for_verify();

        for mut rt in routes_for_verify.as_slice() {
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
            } else {
                let mut rt2;
                if rt.route_type.is_some() && !rt.is_ipv6() {
                    // In nispor, the IPv4 route with route type `Blackhole`,
                    // `Unreachable`, `Prohibit` does not have the route oif
                    // setting.
                    rt2 = rt.clone();
                    rt2.next_hop_iface = None;
                    rt = &rt2
                }

                if !cur_routes.iter().any(|cur_rt| rt.is_match(cur_rt)) {
                    if is_route_delayed_by_nm(rt, current_ifaces) {
                        log::warn!("Route {rt} still missing due to NetworkManager waiting to receive an IP address");
                    }

                    return Err(NmstateError::new(
                        ErrorKind::VerificationError,
                        format!("Desired route {rt} not found after apply"),
                    ));
                }
            }
        }

        Ok(())
    }
}

/// NetworkManager doesn't add routes with ipvx.method auto or dhcp until the
/// interface has at least an IP.
/// This function checks if that's the case. Note that it doesn't check if the
/// route is missing, call this function when you have already checked that.
pub(crate) fn is_route_delayed_by_nm(
    rt: &RouteEntry,
    current_ifaces: &Interfaces,
) -> bool {
    let current_iface = rt.next_hop_iface.as_ref().and_then(|name| {
        current_ifaces.get_iface(name, InterfaceType::Unknown)
    });

    let current_iface_base = match current_iface {
        Some(curr_iface) => curr_iface.base_iface(),
        None => return false,
    };

    let is_auto = if rt.is_ipv6() {
        current_iface_base
            .ipv6
            .as_ref()
            .map(|ipv6| ipv6.is_auto())
            .unwrap_or(false)
    } else {
        current_iface_base
            .ipv4
            .as_ref()
            .map(|ipv4| ipv4.is_auto())
            .unwrap_or(false)
    };

    if !is_auto {
        return false;
    }

    let has_address = if rt.is_ipv6() {
        current_iface_base
            .ipv6
            .as_ref()
            .and_then(|ipv6| ipv6.addresses.as_ref())
            .map(|addrs| !addrs.is_empty())
            .unwrap_or(false)
    } else {
        current_iface_base
            .ipv4
            .as_ref()
            .and_then(|ipv4| ipv4.addresses.as_ref())
            .map(|addrs| !addrs.is_empty())
            .unwrap_or(false)
    };

    !has_address
}
