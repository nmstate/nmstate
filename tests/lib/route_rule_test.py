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

import pytest

from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import RouteRule
from libnmstate.schema import Route

from libnmstate.ifaces import BaseIface
from libnmstate.route import RouteState
from libnmstate.route_rule import RouteRuleEntry
from libnmstate.route_rule import RouteRuleState

from .testlib.ifacelib import gen_two_static_ip_ifaces
from .testlib.ifacelib import gen_two_static_ip_ifaces_different
from .testlib.routelib import IPV4_ROUTE_IFACE_NAME
from .testlib.routelib import IPV4_ROUTE_TABLE_ID
from .testlib.routelib import IPV6_ROUTE_IFACE_NAME
from .testlib.routelib import IPV6_ROUTE_TABLE_ID
from .testlib.routelib import gen_ipv4_route
from .testlib.routelib import gen_ipv6_route


IPV4_ROUTE_RULE_FROM = "198.51.100.0/24"
IPV4_ROUTE_RULE_TO = "198.0.2.0/24"
IPV6_ROUTE_RULE_FROM = "2001:db8:a::/64"
IPV6_ROUTE_RULE_TO = "2001:db8:1::/64"


class TestRouteRuleEntry:
    def test_hash_unique(self):
        rule = _create_route_rule("198.51.100.0/24", "192.0.2.1", 50, 103)
        assert hash(rule) == hash(rule)

    def test_obj_unique(self):
        rule0 = _create_route_rule("198.51.100.0/24", "192.0.2.1", 50, 103)
        rule1 = _create_route_rule("2001:db8:a::/64", "2001:db8:1::a", 51, 104)
        rule0_clone = _create_route_rule(
            "198.51.100.0/24", "192.0.2.1", 50, 103
        )
        assert rule0 == rule0_clone
        assert rule0 != rule1

    def test_obj_unique_without_table(self):
        rule_with_default_table_id = _create_route_rule(
            "198.51.100.0/24",
            "192.0.2.1",
            103,
            RouteRule.USE_DEFAULT_ROUTE_TABLE,
        )

        rule_without_table_id = _create_route_rule(
            "198.51.100.0/24", "192.0.2.1", 103, None
        )

        assert rule_without_table_id == rule_with_default_table_id

    def test_obj_unique_without_priority(self):
        rule_with_default_priority = _create_route_rule(
            "198.51.100.0/24", "192.0.2.1", RouteRule.USE_DEFAULT_PRIORITY, 50
        )

        rule_without_priority = _create_route_rule(
            "198.51.100.0/24", "192.0.2.1", None, 50
        )

        assert rule_without_priority == rule_with_default_priority

    def test_normal_object_as_dict(self):
        rule = _create_route_rule_dict(
            "198.51.100.0/24", "192.0.2.1/32", 50, 103
        )
        rule_obj = RouteRuleEntry(rule)
        assert rule_obj.to_dict() == rule

    @pytest.mark.parametrize(
        "ip_ver_addrs",
        [
            (
                "198.51.100.0",
                "198.51.100.0/32",
                "192.0.2.0/24",
                "192.0.2.0/24",
            ),
            (
                "2001:db8:a::1",
                "2001:db8:a::1/128",
                "2001:db8:b::/64",
                "2001:db8:b::/64",
            ),
            (
                "192.0.2.0/24",
                "192.0.2.0/24",
                "198.51.100.0",
                "198.51.100.0/32",
            ),
            (
                "2001:db8:b::/64",
                "2001:db8:b::/64",
                "2001:db8:a::1",
                "2001:db8:a::1/128",
            ),
        ],
        ids=["ipv4_from", "ipv6_from", "ipv4_to", "ipv6_to"],
    )
    def test_host_only_ip_address(self, ip_ver_addrs):
        ip_from, expected_ip_from, ip_to, expected_ip_to = ip_ver_addrs
        rule = _create_route_rule_dict(ip_from, ip_to, 50, 103)
        expected_rule = _create_route_rule_dict(
            expected_ip_from, expected_ip_to, 50, 103
        )
        rule_obj = RouteRuleEntry(rule)
        assert rule_obj.to_dict() == expected_rule

    @pytest.mark.parametrize(
        "ip_ver_addrs",
        [
            (
                "198.51.100.1/24",
                "198.51.100.0/24",
            ),
            (
                "2001:db8:a::1/64",
                "2001:db8:a::/64",
            ),
        ],
        ids=["ipv4", "ipv6"],
    )
    def test_ip_network_address_with_host_bits(self, ip_ver_addrs):
        ip_addr, expected_ip_addr = ip_ver_addrs
        rule = _create_route_rule_dict(ip_addr, ip_addr, 50, 103)
        expected_rule = _create_route_rule_dict(
            expected_ip_addr, expected_ip_addr, 50, 103
        )
        rule_obj = RouteRuleEntry(rule)
        assert rule_obj.to_dict() == expected_rule

    @pytest.mark.parametrize(
        "ip_ver_addrs",
        [
            (
                "198.51.100.256/24",
                "198.51.100.2/33",
            ),
            (
                "2001:db8:a::ffff0/64",
                "2001:db8:a::/129",
            ),
            ("invalid_ip_string", "invalid_ip_string2"),
        ],
        ids=["ipv4", "ipv6", "invalid_format"],
    )
    def test_invalid_ip_address(self, ip_ver_addrs):
        ip_from, ip_to = ip_ver_addrs
        rule = _create_route_rule_dict(ip_from, ip_to, 50, 103)
        with pytest.raises(NmstateValueError):
            RouteRuleEntry(rule)

    def test_invalid_ipv6_address(self):
        rule = _create_route_rule_dict("256.0.0.0/24", "1.1.1.1/33", 50, 103)
        with pytest.raises(NmstateValueError):
            RouteRuleEntry(rule)

    def test_sort_route_rules(self):
        rules = [
            _create_route_rule("198.51.100.1/24", "192.0.2.1", 50, 103),
            _create_route_rule("198.51.100.0/24", "192.0.2.1", 50, 103),
            _create_route_rule("198.51.100.0/24", "192.0.2.1", 10, 103),
        ]
        expected_rules = [
            _create_route_rule("198.51.100.0/24", "192.0.2.1", 10, 103),
            _create_route_rule("198.51.100.0/24", "192.0.2.1", 50, 103),
            _create_route_rule("198.51.100.1/24", "192.0.2.1", 50, 103),
        ]
        assert expected_rules == sorted(rules)


class TestRouteRuleState:
    def _gen_ifaces(self):
        return gen_two_static_ip_ifaces(
            IPV4_ROUTE_IFACE_NAME, IPV6_ROUTE_IFACE_NAME
        )

    def _gen_ifaces_no_ipv6_one_iface(self):
        return gen_two_static_ip_ifaces_different(
            IPV4_ROUTE_IFACE_NAME, IPV6_ROUTE_IFACE_NAME
        )

    def _gen_route_state(self, ifaces):
        return RouteState(
            ifaces,
            {},
            {
                Route.CONFIG: [
                    gen_ipv4_route().to_dict(),
                    gen_ipv6_route().to_dict(),
                ]
            },
        )

    def test_verify_sort_rules(self):
        ifaces = self._gen_ifaces()
        state = RouteRuleState(
            self._gen_route_state(ifaces),
            {
                RouteRule.CONFIG: [
                    _gen_ipv4_route_rule().to_dict(),
                    _gen_ipv6_route_rule().to_dict(),
                ]
            },
            {},
        )
        state.verify(
            {
                RouteRule.CONFIG: [
                    _gen_ipv6_route_rule().to_dict(),
                    _gen_ipv4_route_rule().to_dict(),
                ]
            }
        )

    def test_verify_sort_rules_no_ipv6_in_one_iface(self):
        ifaces = self._gen_ifaces_no_ipv6_one_iface()
        state = RouteRuleState(
            self._gen_route_state(ifaces),
            {
                RouteRule.CONFIG: [
                    _gen_ipv4_route_rule().to_dict(),
                    _gen_ipv6_route_rule().to_dict(),
                ]
            },
            {},
        )
        state.verify(
            {
                RouteRule.CONFIG: [
                    _gen_ipv6_route_rule().to_dict(),
                    _gen_ipv4_route_rule().to_dict(),
                ]
            }
        )

    def test_gen_metatada(self):
        ifaces = self._gen_ifaces()
        route_state = self._gen_route_state(ifaces)
        route_rule_state = RouteRuleState(
            route_state,
            {
                RouteRule.CONFIG: [
                    _gen_ipv4_route_rule().to_dict(),
                    _gen_ipv6_route_rule().to_dict(),
                ]
            },
            {},
        )
        ifaces.gen_route_rule_metadata(route_rule_state, route_state)

        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]
        ipv6_iface = ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME]

        assert ipv4_iface.to_dict()[Interface.IPV4][
            BaseIface.ROUTE_RULES_METADATA
        ] == [_gen_ipv4_route_rule().to_dict()]
        assert ipv6_iface.to_dict()[Interface.IPV6][
            BaseIface.ROUTE_RULES_METADATA
        ] == [_gen_ipv6_route_rule().to_dict()]

    def test_gen_metatada_no_ipv6_one_iface(self):
        ifaces = self._gen_ifaces_no_ipv6_one_iface()
        route_state = self._gen_route_state(ifaces)
        route_rule_state = RouteRuleState(
            route_state,
            {
                RouteRule.CONFIG: [
                    _gen_ipv4_route_rule().to_dict(),
                    _gen_ipv6_route_rule().to_dict(),
                ]
            },
            {},
        )
        ifaces.gen_route_rule_metadata(route_rule_state, route_state)

        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]
        ipv6_iface = ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME]

        assert ipv4_iface.to_dict()[Interface.IPV4][
            BaseIface.ROUTE_RULES_METADATA
        ] == [_gen_ipv4_route_rule().to_dict()]
        assert ipv6_iface.to_dict()[Interface.IPV6][
            BaseIface.ROUTE_RULES_METADATA
        ] == [_gen_ipv6_route_rule().to_dict()]

    def test_route_rule_to_unknow_route_table(self):
        ifaces = self._gen_ifaces()
        route_state = RouteState(
            ifaces,
            {},
            {Route.CONFIG: [gen_ipv4_route().to_dict()]},
        )
        route_rule_state = RouteRuleState(
            route_state,
            {
                RouteRule.CONFIG: [
                    _gen_ipv4_route_rule().to_dict(),
                    _gen_ipv6_route_rule().to_dict(),
                ]
            },
            {},
        )
        with pytest.raises(NmstateValueError):
            ifaces.gen_route_rule_metadata(route_rule_state, route_state)

    def test_discard_rule_to_unknown_table_when_merging(self):
        ifaces = self._gen_ifaces()
        route_state = RouteState(
            ifaces,
            {},
            {Route.CONFIG: [gen_ipv4_route().to_dict()]},
        )
        route_rule_state = RouteRuleState(
            route_state,
            {},
            {
                RouteRule.CONFIG: [
                    _gen_ipv4_route_rule().to_dict(),
                    _gen_ipv6_route_rule().to_dict(),
                ]
            },
        )
        ifaces.gen_route_rule_metadata(route_rule_state, route_state)
        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]
        ipv6_iface = ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME]

        assert ipv4_iface.to_dict()[Interface.IPV4][
            BaseIface.ROUTE_RULES_METADATA
        ] == [_gen_ipv4_route_rule().to_dict()]
        assert (
            BaseIface.ROUTE_RULES_METADATA
            not in ipv6_iface.to_dict()[Interface.IPV6]
        )

    def test_clear_rules_with_ip_from_using_wildcard(self):
        ifaces = self._gen_ifaces()
        route_state = RouteState(
            ifaces,
            {},
            {Route.CONFIG: [gen_ipv4_route().to_dict()]},
        )
        route_rule_state = RouteRuleState(
            route_state,
            {
                RouteRule.CONFIG: [
                    {
                        RouteRule.IP_FROM: IPV4_ROUTE_RULE_FROM,
                        RouteRule.STATE: RouteRule.STATE_ABSENT,
                    }
                ]
            },
            {
                RouteRule.CONFIG: [
                    {
                        RouteRule.IP_FROM: IPV4_ROUTE_RULE_FROM,
                        RouteRule.IP_TO: "192.0.2.1",
                        RouteRule.PRIORITY: 5000,
                    },
                    {
                        RouteRule.IP_FROM: IPV4_ROUTE_RULE_FROM,
                        RouteRule.IP_TO: IPV4_ROUTE_RULE_TO,
                        RouteRule.PRIORITY: 3000,
                    },
                ]
            },
        )
        ifaces.gen_route_rule_metadata(route_rule_state, route_state)
        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]

        assert (
            BaseIface.ROUTE_RULES_METADATA
            not in ipv4_iface.to_dict()[Interface.IPV4]
        )

    def test_clear_rules_with_ip_to_using_wildcard(self):
        ifaces = self._gen_ifaces()
        route_state = RouteState(
            ifaces,
            {},
            {Route.CONFIG: [gen_ipv4_route().to_dict()]},
        )
        route_rule_state = RouteRuleState(
            route_state,
            {
                RouteRule.CONFIG: [
                    {
                        RouteRule.IP_TO: IPV4_ROUTE_RULE_TO,
                        RouteRule.STATE: RouteRule.STATE_ABSENT,
                    }
                ]
            },
            {
                RouteRule.CONFIG: [
                    {
                        RouteRule.IP_FROM: IPV4_ROUTE_RULE_FROM,
                        RouteRule.IP_TO: IPV4_ROUTE_RULE_TO,
                        RouteRule.PRIORITY: 5000,
                    },
                    {
                        RouteRule.IP_FROM: "192.0.2.0/24",
                        RouteRule.IP_TO: IPV4_ROUTE_RULE_TO,
                        RouteRule.PRIORITY: 3000,
                    },
                ]
            },
        )
        ifaces.gen_route_rule_metadata(route_rule_state, route_state)
        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]

        assert (
            BaseIface.ROUTE_RULES_METADATA
            not in ipv4_iface.to_dict()[Interface.IPV4]
        )

    def test_clear_rules_with_priority_using_wildcard(self):
        ifaces = self._gen_ifaces()
        route_state = RouteState(
            ifaces,
            {},
            {Route.CONFIG: [gen_ipv4_route().to_dict()]},
        )
        route_rule_state = RouteRuleState(
            route_state,
            {
                RouteRule.CONFIG: [
                    {
                        RouteRule.PRIORITY: 5000,
                        RouteRule.STATE: RouteRule.STATE_ABSENT,
                    }
                ]
            },
            {
                RouteRule.CONFIG: [
                    {
                        RouteRule.IP_TO: IPV4_ROUTE_RULE_TO,
                        RouteRule.PRIORITY: 5000,
                    },
                    {
                        RouteRule.IP_TO: IPV4_ROUTE_RULE_TO,
                        RouteRule.PRIORITY: 5000,
                    },
                ]
            },
        )
        ifaces.gen_route_rule_metadata(route_rule_state, route_state)
        ipv4_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]

        assert (
            BaseIface.ROUTE_RULES_METADATA
            not in ipv4_iface.to_dict()[Interface.IPV4]
        )


def _create_route_rule(ip_from, ip_to, priority, table):
    return RouteRuleEntry(
        _create_route_rule_dict(ip_from, ip_to, priority, table)
    )


def _create_route_rule_dict(ip_from, ip_to, priority, table):
    return {
        RouteRule.IP_FROM: ip_from,
        RouteRule.IP_TO: ip_to,
        RouteRule.PRIORITY: priority,
        RouteRule.ROUTE_TABLE: table,
    }


def _gen_ipv4_route_rule():
    return _create_route_rule(
        IPV4_ROUTE_RULE_FROM, IPV4_ROUTE_RULE_TO, 5000, IPV4_ROUTE_TABLE_ID
    )


def _gen_ipv6_route_rule():
    return _create_route_rule(
        IPV6_ROUTE_RULE_FROM, IPV6_ROUTE_RULE_TO, 5001, IPV6_ROUTE_TABLE_ID
    )
