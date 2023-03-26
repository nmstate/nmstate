# SPDX-License-Identifier: LGPL-2.1-or-later

import copy
import logging

from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.error import NmstateNotImplementedError
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

from .dns import DnsState
from .ifaces import Ifaces
from .route import RouteState
from .route_rule import RouteRuleState
from .state import state_match


class NetState:
    def __init__(
        self,
        desire_state,
        ignored_ifnames=None,
        current_state=None,
        save_to_disk=True,
        gen_conf_mode=False,
        ignored_dns_ifaces=None,
    ):
        self.use_global_dns = False
        if current_state is None:
            current_state = {}
        self._ifaces = Ifaces(
            desire_state.get(Interface.KEY),
            current_state.get(Interface.KEY),
            save_to_disk,
            gen_conf_mode,
        )
        if ignored_ifnames is None:
            ignored_ifnames = []
        if ignored_dns_ifaces is None:
            ignored_dns_ifaces = []
        if not gen_conf_mode:
            self._mark_ignored_kernel_ifaces(ignored_ifnames)
        self._route = RouteState(
            self._ifaces,
            desire_state.get(Route.KEY),
            current_state.get(Route.KEY),
        )
        self._dns = DnsState(
            desire_state.get(DNS.KEY),
            current_state.get(DNS.KEY),
        )
        self._route_rule = RouteRuleState(
            self._route,
            desire_state.get(RouteRule.KEY),
            current_state.get(RouteRule.KEY),
        )
        self.desire_state = copy.deepcopy(desire_state)
        self.current_state = copy.deepcopy(current_state)
        if self.desire_state:
            if self._dns.is_46_mixed_dns_servers():
                if gen_conf_mode:
                    raise NmstateNotImplementedError(
                        "Placing IPv4/IPv6 nameserver in the middle of "
                        "IPv6/IPv4 nameservers is not supported yet"
                    )
                else:
                    logging.warning(
                        "Cannot stored IPv4 IPv6 mixed DNS server into "
                        "interface profile, using global DNS"
                    )
                    logging.warning(
                        "Storing DNS to NetworkManager via global dns API, "
                        "this will cause __all__ interface level DNS settings "
                        "been ignored"
                    )
                    self.use_global_dns = True
            else:
                try:
                    self._ifaces.gen_dns_metadata(
                        self._dns, self._route, ignored_dns_ifaces
                    )
                except NmstateValueError as e:
                    if gen_conf_mode:
                        raise e
                    else:
                        logging.warning(
                            "Storing DNS to NetworkManager via global DNS "
                            "API, this will cause __all__ interface level "
                            "DNS settings been ignored"
                        )
                        self.use_global_dns = True

            self._ifaces.gen_route_metadata(self._route)
            self._ifaces.gen_route_rule_metadata(self._route_rule, self._route)
            # DND/Route/RouteRule might introduced new changed interface
            # Regnerate interface metadata
            self._ifaces.gen_metadata()

    def _mark_ignored_kernel_ifaces(self, ignored_ifnames):
        for iface_name in ignored_ifnames:
            iface = self._ifaces.all_kernel_ifaces.get(iface_name)
            if iface and not iface.is_desired:
                iface.mark_as_ignored()

    def verify(self, current_state):
        self._ifaces.verify(current_state.get(Interface.KEY))
        self._dns.verify(current_state.get(DNS.KEY))
        self._route.verify(current_state.get(Route.KEY))
        self._route_rule.verify(current_state.get(RouteRule.KEY))
        self._verify_other_global_info(current_state)

    def _verify_other_global_info(self, current_state):
        for key, value in self.desire_state.items():
            if key not in (Interface.KEY, DNS.KEY, Route.KEY, RouteRule.KEY):
                cur_value = current_state.get(key)
                if not state_match(value, cur_value):
                    raise NmstateVerificationError(
                        format_desired_current_state_diff(
                            {key: value},
                            {key: cur_value},
                        )
                    )

    @property
    def ifaces(self):
        return self._ifaces

    @property
    def dns(self):
        return self._dns
