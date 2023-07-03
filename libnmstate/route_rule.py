#
# Copyright (c) 2020 Red Hat, Inc.
#
# This file is part of nmstate
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

from collections import defaultdict
import logging

from libnmstate.error import NmstateVerificationError
from libnmstate.error import NmstateValueError
from libnmstate.iplib import KERNEL_MAIN_ROUTE_TABLE_ID
from libnmstate.iplib import is_ipv6_address
from libnmstate.iplib import canonicalize_ip_network
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import RouteRule
from libnmstate.schema import Route

from .ifaces.base_iface import BaseIface
from .state import StateEntry
from .state import state_match


class RouteRuleEntry(StateEntry):
    def __init__(self, route_rule):
        self.ip_from = route_rule.get(RouteRule.IP_FROM)
        self.ip_to = route_rule.get(RouteRule.IP_TO)
        self.priority = route_rule.get(RouteRule.PRIORITY)
        self.route_table = route_rule.get(RouteRule.ROUTE_TABLE)
        self.state = route_rule.get(RouteRule.STATE)
        self._complement_defaults()
        self._canonicalize_ip_network()

    def _complement_defaults(self):
        if not self.absent:
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

    def match_with_priority(self, other):
        return self == other or (
            self.priority == RouteRule.USE_DEFAULT_PRIORITY
            and (self.ip_from, self.ip_to, self.route_table)
            == (
                other.ip_from,
                other.ip_to,
                other.route_table,
            )
        )

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
        return self.state == RouteRule.STATE_ABSENT

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
            for entry in _get_config(cur_rule_state):
                rl = RouteRuleEntry(entry)
                self._cur_rules[rl.route_table].add(rl)
                if not route_state or rl.is_valid(
                    route_state.config_iface_routes
                ):
                    self._rules[rl.route_table].add(rl)
        if des_rule_state:
            self._merge_rules(des_rule_state, route_state)

    @property
    def _config(self):
        return _get_config(self._rules)

    def _merge_rules(self, des_rule_state, route_state):
        """
        Handle absent rules before adding desired rule entries to make sure
        absent rule does not delete rule defined in desired state.
        """
        for entry in _get_config(des_rule_state):
            rl = RouteRuleEntry(entry)
            if rl.absent:
                self._apply_absent_rules(rl)
        for entry in _get_config(des_rule_state):
            rl = RouteRuleEntry(entry)
            if not rl.absent:
                if any(
                    exist_rule
                    for exist_rule in self._rules[rl.route_table]
                    if rl.match_with_priority(exist_rule)
                ):
                    continue
                self._rules[rl.route_table].add(rl)

    def _apply_absent_rules(self, rl):
        """
        Remove rules based on absent rules and treat missing property as
        wildcard match.
        """
        absent_iface_table = rl.route_table
        for route_table, rule_set in self._rules.items():
            if absent_iface_table and absent_iface_table != route_table:
                continue
            new_rules = set()
            for rule in rule_set:
                if not rl.match(rule):
                    new_rules.add(rule)
            if new_rules != rule_set:
                self._rules[route_table] = new_rules

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

    def gen_metadata(self, route_state, ifaces):
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
        route_rule_metadata = defaultdict(
            lambda: {Interface.IPV4: [], Interface.IPV6: []}
        )
        for route_table, rules in self._rules.items():
            rules_ipfamily = {Interface.IPV4: set(), Interface.IPV6: set()}
            cur_rules_ipfamily = {Interface.IPV4: set(), Interface.IPV6: set()}
            for rule in self._cur_rules[route_table]:
                cur_rules_ipfamily[
                    Interface.IPV6 if rule.is_ipv6 else Interface.IPV4
                ].add(rule)
            for rule in rules:
                rules_ipfamily[
                    Interface.IPV6 if rule.is_ipv6 else Interface.IPV4
                ].add(rule)
            if len(rules_ipfamily[Interface.IPV4]) != 0:
                self._add_rule_to_matadata(
                    route_state,
                    ifaces,
                    Interface.IPV4,
                    route_table,
                    cur_rules_ipfamily,
                    rules_ipfamily,
                    route_rule_metadata,
                )
            if len(rules_ipfamily[Interface.IPV6]) != 0:
                self._add_rule_to_matadata(
                    route_state,
                    ifaces,
                    Interface.IPV6,
                    route_table,
                    cur_rules_ipfamily,
                    rules_ipfamily,
                    route_rule_metadata,
                )
        return route_rule_metadata

    def _add_rule_to_matadata(
        self,
        route_state,
        ifaces,
        ip_family,
        route_table,
        cur_rules_ipfamily,
        rules_ipfamily,
        route_rule_metadata,
    ):
        iface_name = self._iface_for_route_table(
            route_state, route_table, ifaces, ip_family
        )
        if route_rule_metadata.get(iface_name) is None:
            route_rule_metadata[iface_name] = {
                Interface.IPV4: [],
                Interface.IPV6: [],
            }
        if rules_ipfamily[ip_family] != cur_rules_ipfamily[ip_family]:
            route_rule_metadata[iface_name][
                BaseIface.RULE_CHANGED_METADATA
            ] = True
        for rule in rules_ipfamily[ip_family]:
            route_rule_metadata[iface_name][ip_family].append(rule.to_dict())

    def _iface_for_route_table(
        self, route_state, route_table, ifaces, ip_family
    ):
        for routes in route_state.config_iface_routes.values():
            for route in routes:
                if route.table_id == route_table and ifaces.get(
                    route.next_hop_interface, {}
                ).to_dict().get(ip_family, {}).get(InterfaceIP.ENABLED):
                    return route.next_hop_interface

        for iface in ifaces.values():
            autotable_ipv4 = (
                iface.to_dict()
                .get(Interface.IPV4, {})
                .get(InterfaceIP.AUTO_ROUTE_TABLE_ID)
            )
            autotable_ipv6 = (
                iface.to_dict()
                .get(Interface.IPV6, {})
                .get(InterfaceIP.AUTO_ROUTE_TABLE_ID)
            )
            if autotable_ipv4 == route_table or autotable_ipv6 == route_table:
                return iface.name

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
