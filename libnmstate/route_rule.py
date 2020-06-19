from collections import defaultdict
import logging

from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateVerificationError
from libnmstate.error import NmstateValueError
from libnmstate.iplib import KERNEL_MAIN_ROUTE_TABLE_ID
from libnmstate.iplib import is_ipv6_address
from libnmstate.iplib import canonicalize_ip_network
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import Interface
from libnmstate.schema import RouteRule
from libnmstate.schema import Route

from .state import StateEntry
from .state import state_match


class RouteRuleEntry(StateEntry):
    def __init__(self, route_rule):
        self.ip_from = route_rule.get(RouteRule.IP_FROM)
        self.ip_to = route_rule.get(RouteRule.IP_TO)
        self.priority = route_rule.get(RouteRule.PRIORITY)
        self.route_table = route_rule.get(RouteRule.ROUTE_TABLE)
        self._complement_defaults()
        self._canonicalize_ip_network()

    def _complement_defaults(self):
        if self.ip_from is None:
            self.ip_from = ""
        if self.ip_to is None:
            self.ip_to = ""
        if self.priority is None:
            self.priority = RouteRule.USE_DEFAULT_PRIORITY
        if (
            self.route_table is None
            or self.route_table == RouteRule.USE_DEFAULT_ROUTE_TABLE
        ):
            self.route_table = KERNEL_MAIN_ROUTE_TABLE_ID

    def _canonicalize_ip_network(self):
        if self.ip_from:
            self.ip_from = canonicalize_ip_network(self.ip_from)
        if self.ip_to:
            self.ip_to = canonicalize_ip_network(self.ip_to)

    def _keys(self):
        return (self.ip_from, self.ip_to, self.priority, self.route_table)

    @property
    def is_ipv6(self):
        if self.ip_from:
            return is_ipv6_address(self.ip_from)
        elif self.ip_to:
            return is_ipv6_address(self.ip_to)
        else:
            logging.warning(
                f"Neither {RouteRule.IP_FROM} nor {RouteRule.IP_TO} "
                "is defined, treating it a IPv4 route rule"
            )
            return False

    @property
    def absent(self):
        raise NmstateNotImplementedError(
            "RouteRuleEntry does not support absent property"
        )

    def is_valid(self, config_iface_routes):
        """
        Return False when there is no route for defined route table.
        """
        found = False
        for route_set in config_iface_routes.values():
            for route in route_set:
                if route.table_id == self.route_table or (
                    route.table_id == Route.USE_DEFAULT_ROUTE_TABLE
                    and self.route_table == KERNEL_MAIN_ROUTE_TABLE_ID
                ):
                    found = True
                    break
        return found


class RouteRuleState:
    def __init__(self, route_state, des_rule_state, cur_rule_state):
        self._config_changed = False
        self._cur_rules = defaultdict(set)
        self._rules = defaultdict(set)
        if cur_rule_state:
            for rule_dict in _get_config(cur_rule_state):
                rule = RouteRuleEntry(rule_dict)
                self._cur_rules[rule.route_table].add(rule)
        if des_rule_state:
            for rule_dict in _get_config(des_rule_state):
                rule = RouteRuleEntry(rule_dict)
                self._rules[rule.route_table].add(rule)
            if self._rules != self._cur_rules:
                self._config_changed = True
        else:
            # Discard invalid route rule when merging from current
            for rules in self._cur_rules.values():
                for rule in rules:
                    if not route_state or rule.is_valid(
                        route_state.config_iface_routes
                    ):
                        self._rules[rule.route_table].add(rule)

    @property
    def _config(self):
        return _get_config(self._rules)

    def verify(self, cur_rule_state):
        current = RouteRuleState(
            route_state=None,
            des_rule_state=None,
            cur_rule_state=cur_rule_state,
        )
        for route_table, rules in self._rules.items():
            rule_info = [
                _remove_route_rule_default_values(r.to_dict())
                for r in sorted(rules)
            ]
            cur_rule_info = [
                r.to_dict()
                for r in sorted(current._rules.get(route_table, set()))
            ]

            if not state_match(rule_info, cur_rule_info):
                raise NmstateVerificationError(
                    format_desired_current_state_diff(
                        {RouteRule.KEY: {RouteRule.CONFIG: rule_info}},
                        {RouteRule.KEY: {RouteRule.CONFIG: cur_rule_info}},
                    )
                )

    @property
    def config_changed(self):
        return self._config_changed

    def gen_metadata(self, route_state):
        """
        Generate metada which could used for storing into interface.
        Data structure returned is:
            {
                iface_name: {
                    Interface.IPV4: ipv4_route_rules,
                    Interface.IPV6: ipv6_route_rules,
                }
            }
        """
        route_rule_metadata = {}
        for route_table, rules in self._rules.items():
            iface_name = self._iface_for_route_table(route_state, route_table)
            route_rule_metadata[iface_name] = {
                Interface.IPV4: [],
                Interface.IPV6: [],
            }
            for rule in rules:
                family = Interface.IPV6 if rule.is_ipv6 else Interface.IPV4
                route_rule_metadata[iface_name][family].append(rule.to_dict())
        return route_rule_metadata

    def _iface_for_route_table(self, route_state, route_table):
        for routes in route_state.config_iface_routes.values():
            for route in routes:
                if route.table_id == route_table:
                    return route.next_hop_interface
        raise NmstateValueError(
            "Failed to find interface to with route table ID "
            f"{route_table} to store route rules"
        )


def _get_config(state):
    return state.get(RouteRule.CONFIG, [])


def _remove_route_rule_default_values(rule):
    if rule.get(RouteRule.PRIORITY) == RouteRule.USE_DEFAULT_PRIORITY:
        del rule[RouteRule.PRIORITY]
    if rule.get(RouteRule.ROUTE_TABLE) == RouteRule.USE_DEFAULT_ROUTE_TABLE:
        del rule[RouteRule.ROUTE_TABLE]
    return rule
