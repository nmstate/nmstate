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

from libnmstate.schema import RouteRule


NISPOR_RULE_ACTION_TABLE = "table"


def nispor_route_rule_state_to_nmstate(np_rules):
    return [
        _nispor_route_rule_to_nmstate(rl)
        for rl in np_rules
        if (rl.src or rl.dst) and rl.action == NISPOR_RULE_ACTION_TABLE
    ]


def _nispor_route_rule_to_nmstate(np_rl):
    rule = {
        RouteRule.ROUTE_TABLE: np_rl.table,
        RouteRule.PRIORITY: np_rl.priority
        if np_rl.priority
        else RouteRule.USE_DEFAULT_PRIORITY,
    }
    if np_rl.src:
        rule[RouteRule.IP_FROM] = np_rl.src
    if np_rl.dst:
        rule[RouteRule.IP_TO] = np_rl.dst
    return rule
